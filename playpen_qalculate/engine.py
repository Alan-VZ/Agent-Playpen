"""Bounded subprocess interface to Qalculate's official qalc executable."""

from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import unicodedata


FUNCTIONS = frozenset(
    "abs sqrt cbrt root exp ln log log10 log2 sin cos tan asin acos atan atan2 sinh cosh tanh asinh acosh atanh sinc floor ceil round trunc sign min max sum product mean median stdev variance factorial gcd lcm mod rem solve solve2 multisolve diff integrate limit simplify factorize expand det inverse transpose rank trace dot cross norm magnitude real imag arg conj polar cis uncertainty interval lower upper midpoint genvector vector matrix element if".split()
)
FORBIDDEN = frozenset(
    "load export save store function variable delete plot command system exec shell exrates download fetch run import read write history quit exit set help info list ans answer rand random randn montecarlo today tomorrow yesterday now uptime timestamp".split()
)
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?\Z")


class CalculationError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def checked_expression(value, *, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise CalculationError(
            "invalid_expression",
            f"Supply a mathematical expression of 1–{limit} characters.",
        )
    value = (
        unicodedata.normalize("NFKC", value)
        .strip()
        .replace("−", "-")
        .replace("×", "*")
        .replace("÷", "/")
    )
    if any(not (c.isalnum() or c in "_ +-*/^%=!<>().,;[]") for c in value):
        raise CalculationError(
            "invalid_expression",
            "Use mathematics, identifiers and units only; no quotes, paths, commands, scripts or newlines.",
        )
    if any(c in value for c in ["\n", "\r", ":=", "//", "..", "&&", "||"]):
        raise CalculationError(
            "invalid_expression",
            "Commands, assignments, paths and scripts are unavailable.",
        )
    identifiers = re.findall(r"[^\W\d]\w*", value, flags=re.UNICODE)
    if any(name.casefold() in FORBIDDEN for name in identifiers):
        raise CalculationError(
            "blocked_operation",
            "File, command, network, persistent-state and random/time operations are unavailable.",
        )
    for match in re.finditer(r"([^\W\d]\w*)\s*\(", value, flags=re.UNICODE):
        if match.group(1).casefold() not in FUNCTIONS:
            raise CalculationError(
                "unsupported_function",
                f"Unsupported function: {match.group(1)}. Use explicit multiplication, e.g. x*(x+1).",
            )
    stack = []
    for c in value:
        if c in "([":
            stack.append(c)
        elif c in ")]":
            if not stack or stack.pop() != ("]" == c and "[" or "("):
                raise CalculationError(
                    "invalid_expression", "Unbalanced expression delimiters."
                )
    if stack:
        raise CalculationError(
            "invalid_expression", "Unbalanced expression delimiters."
        )
    return value


def checked_bindings(variables):
    if variables is None:
        return {}
    if not isinstance(variables, dict) or len(variables) > 20:
        raise CalculationError(
            "invalid_variables",
            "Variables must be a mapping of at most 20 names to numeric/unit expressions.",
        )
    result = {}
    for name, value in variables.items():
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", name)
            or name.casefold() in FORBIDDEN | FUNCTIONS | {"where", "and", "or", "to"}
        ):
            raise CalculationError(
                "invalid_variables",
                "Use simple non-reserved variable names, e.g. distance or mass.",
            )
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise CalculationError(
                "invalid_variables",
                "Supply exact values as strings (not binary floats), e.g. '0.1' or '12 kg'.",
            )
        result[name] = checked_expression(str(value), limit=300)
    return result


class QalculateEngine:
    def __init__(
        self, executable=None, *, work_dir=None, timeout=15, max_output=262144
    ):
        self.executable = str(
            executable or os.environ.get("QALCULATE_QALC") or shutil.which("qalc") or ""
        )
        self.work_dir = Path(work_dir) if work_dir else None
        self.timeout = float(timeout)
        if not 0.1 <= self.timeout <= 30 or not 4096 <= max_output <= 1048576:
            raise ValueError("Invalid engine resource limits")
        self.max_output = max_output

    def available(self):
        return bool(self.executable and Path(self.executable).is_file())

    def _require(self):
        if not self.available():
            raise CalculationError(
                "dependency_missing",
                "qalc is unavailable. Install Qalculate's official CLI and set QALCULATE_QALC or pass executable.",
            )

    def _process(self, argv, directory, deadline):
        self._require()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CalculationError("timeout", "Calculation exceeded its time limit.")
        env = {
            k: v
            for k, v in os.environ.items()
            if k.upper()
            in {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "SYSTEMDRIVE"}
        }
        env.update(
            {
                "QALCULATE_USER_DIR": str(directory),
                "HOME": str(directory),
                "APPDATA": str(directory),
                "LOCALAPPDATA": str(directory),
                "XDG_CONFIG_HOME": str(directory),
                "XDG_DATA_HOME": str(directory),
                "XDG_CACHE_HOME": str(directory),
                "LANG": "C",
                "LC_ALL": "C",
            }
        )
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            process = subprocess.Popen(
                [self.executable, *argv],
                cwd=directory,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                creationflags=flags,
            )
        except OSError:
            raise CalculationError(
                "engine_unavailable",
                "Cannot start qalc. Check its executable and runtime dependencies.",
            ) from None
        output = [bytearray(), bytearray()]
        too_large = threading.Event()

        def drain(stream, index):
            try:
                while chunk := stream.read(4096):
                    if len(output[index]) + len(chunk) > self.max_output:
                        too_large.set()
                        process.kill()
                        break
                    output[index].extend(chunk)
            finally:
                stream.close()

        threads = [
            threading.Thread(target=drain, args=(process.stdout, 0), daemon=True),
            threading.Thread(target=drain, args=(process.stderr, 1), daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise CalculationError(
                "timeout", "Calculation exceeded its time limit; qalc was terminated."
            ) from None
        finally:
            for thread in threads:
                thread.join(timeout=2)
        if too_large.is_set():
            raise CalculationError(
                "output_limit", "Calculation output exceeded the tool limit."
            )
        stdout, stderr = [x.decode("utf-8", errors="replace").strip() for x in output]
        if process.returncode:
            raise CalculationError(
                "engine_error", (stderr or stdout or "qalc failed")[:2000]
            )
        return stdout, stderr

    def evaluate(
        self,
        expression,
        *,
        variables=None,
        precision=50,
        mode="approximate",
        angle_unit="radians",
        _allow_diagnostics=False,
        _deadline=None,
    ):
        expression = checked_expression(expression)
        bindings = checked_bindings(variables)
        if type(precision) is not int or not 10 <= precision <= 200:
            raise CalculationError(
                "invalid_precision",
                "Precision must be an integer from 10 to 200 significant digits.",
            )
        if mode not in {"approximate", "exact", "try exact"} or angle_unit not in {
            "radians",
            "degrees",
        }:
            raise CalculationError(
                "invalid_mode",
                "Choose exact, approximate or try exact; angle unit radians or degrees.",
            )
        parts = re.split(r"\s+to\s+", expression, maxsplit=1)
        submitted = parts[0] if not bindings else f"({parts[0]})"
        if bindings:
            submitted += " where " + " and ".join(
                f"{name}=({value})" for name, value in bindings.items()
            )
        if len(parts) == 2:
            submitted += " to " + parts[1]
        options = [
            "--defaults",
            "--nocurrencies",
            "--nodatasets",
            "--time",
            str(int(self.timeout * 1000)),
        ]
        for setting in [
            f"precision {precision}",
            f"approximation {mode}",
            "fractions exact" if mode != "approximate" else "fractions off",
            f"angle {angle_unit}",
            "unicode off",
            "decimal comma off",
            "digit grouping off",
            "read precision off",
            "unknowns on",
            "update exchange rates 0",
            "save config no",
            "save definitions no",
            "save mode no",
            "ignore locale yes",
        ]:
            options += ["--set", setting]
        if self.work_dir:
            self.work_dir.mkdir(parents=True, exist_ok=True)
        deadline = min(time.monotonic() + self.timeout, _deadline or float("inf"))
        with tempfile.TemporaryDirectory(prefix="qalc-", dir=self.work_dir) as temp:
            directory = Path(temp)
            # Terse qalc suppresses diagnostic messages, including division by
            # zero. Validate once with diagnostics before obtaining raw result.
            diagnostic, stderr = self._process(
                [*options, "--", submitted], directory, deadline
            )
            warnings = [
                line.strip()
                for line in (diagnostic + "\n" + stderr).splitlines()
                if re.match(r"\s*(warning|error|fatal):", line, re.I)
            ]
            if warnings and not _allow_diagnostics:
                raise CalculationError(
                    "calculation_diagnostic", " ".join(warnings)[:2000]
                )
            result, stderr = self._process(
                [*options, "--terse", "--", submitted], directory, deadline
            )
            if not result or stderr:
                raise CalculationError(
                    "calculation_failed", (stderr or "qalc returned no result")[:2000]
                )
            version, _ = self._process(["--version"], directory, deadline)
        return {
            "ok": True,
            "operation": "evaluate",
            "calculation_id": uuid.uuid4().hex,
            "engine": "Qalculate/qalc",
            "engine_version": version.splitlines()[0],
            "expression": expression,
            "variables": bindings,
            "submitted_expression": submitted,
            "precision_digits": precision,
            "mode": mode,
            "angle_unit": angle_unit,
            "result": result,
            "result_format": "qalculate_text",
            "numeric": bool(NUMBER.fullmatch(result)),
            "warnings": warnings,
        }

    def plot(
        self,
        expression,
        *,
        output_dir,
        variable="x",
        x_min="-10",
        x_max="10",
        points=201,
        precision=50,
        variables=None,
        angle_unit="radians",
    ):
        from .plotting import make_plot

        return make_plot(
            self,
            expression,
            output_dir=output_dir,
            variable=variable,
            x_min=x_min,
            x_max=x_max,
            points=points,
            precision=precision,
            variables=variables,
            angle_unit=angle_unit,
        )


def decimal_value(value):
    if (
        not isinstance(value, str)
        or len(value) > 200
        or not NUMBER.fullmatch(value.strip())
    ):
        raise CalculationError(
            "invalid_range", "Plot bounds must be decimal strings, e.g. '-10' and '10'."
        )
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise CalculationError("invalid_range", "Invalid decimal value") from None
    if not result.is_finite() or abs(result) > Decimal("1e100"):
        raise CalculationError(
            "invalid_range", "Plot bounds must be finite and within ±1e100."
        )
    return result
