"""Playpen adapters for the shared Universal Agent Control Plane gateway."""

from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path

from config.credentials import redact
from universal_agent_control_plane.tool_gateway import ToolGateway, ToolSpec


def tool_spec(tool):
    parameters = deepcopy(tool.to_openai_schema()["function"]["parameters"])
    parameters.setdefault("additionalProperties", False)
    for value in parameters.get("properties", {}).values():
        if value.get("type") == "string":
            value.setdefault("maxLength", 65536)
    try:
        source = inspect.getsource(type(tool))
    except (TypeError, OSError):
        source = type(tool).__module__ + "." + type(tool).__qualname__
    digest = hashlib.sha256(
        (source + json.dumps(parameters, sort_keys=True)).encode()
    ).hexdigest()[:16]
    name = tool.name

    def readiness():
        if name == "scientific_calculator":
            from tools.packs.utils.scientific_calculator_tool import configured_engine

            engine, _ = configured_engine()
            return {
                "ready": engine.available(),
                "status": "available" if engine.available() else "dependency_missing",
                "message": "Local qalc executable present; an actual calculation verifies operation."
                if engine.available()
                else "Configure QALCULATE_QALC or config/qalculate.json.",
            }
        if name == "nimble_extract":
            from config.credentials import get_credential

            ready = bool(get_credential("NIMBLE_API_KEY"))
            return {
                "ready": ready,
                "status": "saved_unverified" if ready else "missing_key",
                "message": "Use Secrets & API inventory to check access; no paid request was made.",
            }
        return {
            "ready": True,
            "status": "configured_unverified",
            "message": "Registered; no external request was made. Use API inventory for provider access checks.",
        }

    return ToolSpec(
        name=name,
        description=tool.description,
        input_schema=parameters,
        handler=tool.run,
        version=digest,
        read_only=name
        in {
            "calculator",
            "datetime",
            "web_search",
            "fetch",
            "read_file",
            "read_fixture",
            "nimble_extract",
        },
        replay_safe=name == "calculator",
        readiness=readiness,
        source=type(tool).__module__,
    )


def build_gateway(registry, *, event=None, database=None):
    gateway = ToolGateway(redact=redact, event=event, database=database)
    for name in registry.list_all():
        gateway.register(tool_spec(registry.get(name)))
    return gateway


def default_registry(
    *, allowed_dirs=None, search_provider="auto", include_writes=False
):
    from tools.tool_registry import ToolRegistry
    from tools.packs.utils.calculator_tool import CalculatorTool
    from tools.packs.utils.scientific_calculator_tool import ScientificCalculatorTool
    from tools.packs.utils.datetime_tool import DatetimeTool
    from tools.packs.web.search_tool import WebSearchTool
    from tools.packs.web.fetch_tool import FetchTool
    from tools.packs.web.nimble_extract import NimbleExtractTool
    from tools.packs.filesystem.read_file import ReadFileTool
    from tools.packs.filesystem.write_file import WriteFileTool

    registry = ToolRegistry()
    dirs = [str(Path(d).resolve()) for d in (allowed_dirs or ["."])]
    tools = [
        CalculatorTool(),
        ScientificCalculatorTool(),
        DatetimeTool(),
        WebSearchTool(provider=search_provider),
        FetchTool(),
        NimbleExtractTool(),
        ReadFileTool(allowed_dirs=dirs),
    ]
    if include_writes:
        tools.append(WriteFileTool(allowed_dirs=dirs, safe_mode=True))
    for tool in tools:
        registry.register(tool)
    return registry
