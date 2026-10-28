from __future__ import annotations

import json
import os
import secrets
import re
import threading
import uuid
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from dotenv import dotenv_values

from config import credentials
from config.credentials import get_credential, redact, CredentialError
from config.security import azure_endpoint
from pydantic import BaseModel, Field, ValidationError

from backends.backend_factory import BackendFactory
from core.agent import Agent
from debugging.tracer import Tracer
from memory.memory_manager import MemoryManager
from planner.cot_planner import CoTPlanner
from planner.react_planner import ReActPlanner
from planner.tree_planner import TreePlanner
from tools.packs.filesystem.read_file import ReadFileTool
from tools.packs.filesystem.write_file import WriteFileTool
from tools.packs.utils.calculator_tool import CalculatorTool
from tools.packs.utils.datetime_tool import DatetimeTool
from tools.packs.web.fetch_tool import FetchTool
from tools.packs.web.search_tool import WebSearchTool
from tools.tool_registry import ToolRegistry

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "debugging" / "dashboard" / "templates"
ENV_PATH = ROOT / ".env"
_SETTINGS_LOCK = threading.RLock()

BACKEND_KEY_VAR = {
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "together": "TOGETHER_API_KEY",
    "azure_openai": "AZURE_OPENAI_KEY",
}

SEARCH_KEY_VAR = {
    "tavily": "TAVILY_API_KEY",
    "serpapi": "SERPAPI_API_KEY",
    "google": "GOOGLE_API_KEY",
}

SEARCH_EXTRA_VAR = {
    "google": "GOOGLE_CSE_ID",
}

MANAGED_KEYS = sorted(set(BACKEND_KEY_VAR.values()) | set(SEARCH_KEY_VAR.values()) | set(SEARCH_EXTRA_VAR.values()))


def _read_env_file() -> dict[str, str]:
    """Parse .env into a dict. Missing file yields an empty dict."""
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    values = {k: v for k, v in dotenv_values(ENV_PATH, interpolate=False, encoding="utf-8-sig").items() if v is not None}
    return values


def _write_env_file(updates: dict[str, str | None]) -> None:
    """
    Merge updates into .env, preserving every unrelated line, comment and
    blank line. A value of None deletes that entry.
    """
    with _SETTINGS_LOCK:
        lines = ENV_PATH.read_text(encoding="utf-8-sig").splitlines() if ENV_PATH.exists() else []
        pending = dict(updates)
        output: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                output.append(line)
                continue
            match = re.match(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", stripped)
            if not match:
                output.append(line)
                continue
            key = match.group(1)
            if key in updates:
                value = pending.pop(key, None)
                if value is not None:
                    output.append(f"{key}={json.dumps(value)}")
            else:
                output.append(line)

        for key, value in pending.items():
            if value is not None:
                output.append(f"{key}={json.dumps(value)}")

        ENV_PATH.write_text("\n".join(output).rstrip("\n") + "\n", encoding="utf-8")


def _load_env_into_process() -> None:
    """Make saved .env values visible to os.getenv without python-dotenv."""
    for key, value in _read_env_file().items():
        if key not in MANAGED_KEYS:
            os.environ.setdefault(key, value)
        else:
            credentials.remember_secret(value)


_load_env_into_process()

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app = FastAPI(title="Agent Playpen Web Wrapper", version="1.1.0", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])
API_TOKEN = secrets.token_urlsafe(32)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic's default errors include input values, which may contain a key.
    return JSONResponse(status_code=422, content={"message": "Invalid request fields."})


@app.middleware("http")
async def local_session_boundary(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse(status_code=403, content={"message": "Cross-origin API access denied."})
        if not secrets.compare_digest(request.headers.get("x-playpen-token", ""), API_TOKEN):
            return JSONResponse(status_code=403, content={"message": "Open the local dashboard to establish a session."})
        if "api_key" in request.query_params:
            return JSONResponse(status_code=400, content={"message": "Credentials are not accepted in URLs. Use the credential manager."})
        # Register all available secrets so accidental echoes are redacted.
        for name in MANAGED_KEYS:
            get_credential(name)
    try:
        response = await call_next(request)
        if request.url.path.startswith("/api/") and "application/json" in response.headers.get("content-type", ""):
            body = b"".join([part async for part in response.body_iterator])
            response = JSONResponse(content=redact(json.loads(body)), status_code=response.status_code)
    except Exception:
        response = JSONResponse(status_code=500, content={"status": "error", "message": "Operation failed. Check local configuration and provider availability."})
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = f"default-src 'self'; script-src 'self' 'nonce-{API_TOKEN}'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response

PLANNER_MAP = {
    "react": ReActPlanner,
    "cot": CoTPlanner,
    "tree": TreePlanner,
}

TOOL_CHOICES = [
    "web_search",
    "fetch",
    "read_file",
    "write_file",
    "calculator",
    "datetime",
]

FALLBACK_MODELS = {
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
    "openrouter": [
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
        "anthropic/claude-3.5-sonnet",
        "meta-llama/llama-3.1-8b-instruct",
    ],
    "anthropic": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
    ],
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "gemma2-9b-it",
    ],
    "together": [
        "meta-llama/Llama-3-70b-chat-hf",
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
    ],
    "lm_studio": ["local-model"],
    "ollama": ["llama3.1:8b", "mistral", "qwen2.5:7b"],
    "azure_openai": [],
}


def _require_key(value: str, backend: str) -> str:
    if not value:
        raise RuntimeError(
            f"An API key is required to list models for '{backend}'. "
            "Enter one and press Save, or type the model name manually."
        )
    return value


def _fetch_models(backend: str, base_url: str, api_key: str) -> list[str]:
    """Query the provider for its available models. Raises on failure."""
    timeout = 10

    if backend == "lm_studio":
        url = (base_url or "http://localhost:1234/v1").rstrip("/") + "/models"
        response = requests.get(url, timeout=timeout, allow_redirects=False)
        response.raise_for_status()
        return sorted(m["id"] for m in response.json().get("data", []))

    if backend == "ollama":
        root = (base_url or "http://localhost:11434").rstrip("/")
        if root.endswith("/v1"):
            root = root[: -len("/v1")]
        response = requests.get(f"{root}/api/tags", timeout=timeout, allow_redirects=False)
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        names: list[str] = []
        for item in models:
            if isinstance(item, dict):
                name = item.get("name") or item.get("model")
                if name:
                    names.append(name)
            elif isinstance(item, str) and item.strip():
                names.append(item.strip())
        return sorted(set(names))

    if backend in {"openai", "groq", "together", "openrouter"}:
        endpoints = {
            "openai": "https://api.openai.com/v1/models",
            "openrouter": "https://openrouter.ai/api/v1/models",
            "groq": "https://api.groq.com/openai/v1/models",
            "together": "https://api.together.xyz/v1/models",
        }
        key = get_credential(BACKEND_KEY_VAR[backend], api_key) if backend != "openrouter" else ""
        if backend != "openrouter":
            key = _require_key(key, backend)
        response = requests.get(
            endpoints[backend],
            headers={"Authorization": "Bearer " + key} if key else {},
            timeout=timeout,
            allow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
        entries = payload.get("data", payload) if isinstance(payload, dict) else payload
        return sorted(e["id"] for e in entries if isinstance(e, dict) and e.get("id"))

    if backend == "anthropic":
        key = _require_key(get_credential("ANTHROPIC_API_KEY", api_key), backend)
        response = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            timeout=timeout,
            allow_redirects=False,
        )
        response.raise_for_status()
        return sorted(m["id"] for m in response.json().get("data", []))

    return []


class AgentConfig(BaseModel):
    backend: str = "lm_studio"
    model: str = "local-model"
    base_url: str = "http://localhost:1234/v1"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = Field(default=2048, ge=1)
    planner: str = "react"
    tools: list[str] = Field(default_factory=lambda: ["web_search", "fetch", "calculator"])
    task: str = ""
    max_iterations: int = Field(default=10, ge=1)
    allowed_dirs: str = "."
    search_provider: str = "auto"
    search_cse_id: str = ""

    model_config = {"extra": "ignore"}


def _tool_factory(name: str, config: AgentConfig):
    dirs = [d.strip() for d in config.allowed_dirs.split(",") if d.strip()] or ["."]

    if name == "web_search":
        key_var = SEARCH_KEY_VAR.get(config.search_provider)
        search_key = get_credential(key_var) if key_var else ""
        cse_var = SEARCH_EXTRA_VAR.get(config.search_provider)
        search_cse_id = get_credential(cse_var) if cse_var else ""
        return WebSearchTool(provider=config.search_provider, api_key=search_key or None, cse_id=search_cse_id or None)
    if name == "fetch":
        return FetchTool()
    if name == "read_file":
        return ReadFileTool(allowed_dirs=dirs)
    if name == "write_file":
        return WriteFileTool(allowed_dirs=dirs, safe_mode=True)
    if name == "python_repl":
        raise ValueError("Unrestricted Python execution is unavailable in the credential-enabled dashboard.")
    if name == "calculator":
        return CalculatorTool()
    if name == "datetime":
        return DatetimeTool()
    raise ValueError(f"Unsupported tool: {name}")


def _build_backend(config: AgentConfig):
    kwargs = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }

    if config.backend == "lm_studio":
        kwargs["base_url"] = config.base_url
        backend = BackendFactory.create("lm_studio", **kwargs)
    elif config.backend == "openai":
        kwargs["api_key"] = get_credential("OPENAI_API_KEY", config.api_key)
        kwargs["org_id"] = os.getenv("OPENAI_ORG_ID")
        backend = BackendFactory.create("openai", **kwargs)
    elif config.backend == "openrouter":
        kwargs["model"] = config.model if config.model not in {"", "local-model"} else os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        kwargs["api_key"] = get_credential("OPENROUTER_API_KEY", config.api_key)
        kwargs["base_url"] = "https://openrouter.ai/api/v1"
        backend = BackendFactory.create("openrouter", **kwargs)
    elif config.backend == "anthropic":
        kwargs.pop("temperature")
        kwargs["api_key"] = get_credential("ANTHROPIC_API_KEY", config.api_key)
        backend = BackendFactory.create("anthropic", **kwargs)
    elif config.backend == "azure_openai":
        kwargs.pop("model")
        kwargs["api_key"] = get_credential("AZURE_OPENAI_KEY", config.api_key)
        kwargs["azure_endpoint"] = azure_endpoint(os.getenv("AZURE_OPENAI_ENDPOINT", ""))
        kwargs["deployment_name"] = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        kwargs["api_version"] = os.getenv("AZURE_OPENAI_API_VERSION") or "2024-05-01-preview"
        backend = BackendFactory.create("azure_openai", **kwargs)
    elif config.backend == "groq":
        kwargs["api_key"] = get_credential("GROQ_API_KEY", config.api_key)
        backend = BackendFactory.create("groq", **kwargs)
    elif config.backend == "together":
        kwargs["api_key"] = get_credential("TOGETHER_API_KEY", config.api_key)
        kwargs["model"] = config.model or os.getenv("TOGETHER_MODEL", "meta-llama/Llama-3-70b-chat-hf")
        backend = BackendFactory.create("together", **kwargs)
    elif config.backend == "ollama":
        kwargs["base_url"] = config.base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        backend = BackendFactory.create("ollama", **kwargs)
    else:
        raise ValueError(f"Unsupported backend: {config.backend}")

    if hasattr(backend, "health_check"):
        try:
            if not backend.health_check():
                raise RuntimeError(f"Backend '{config.backend}' reported unhealthy status.")
        except Exception as exc:
            raise RuntimeError(f"Backend '{config.backend}' could not be reached: {exc}") from exc

    return backend


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "session_token": API_TOKEN,
            "backends": list(BackendFactory.REGISTRY.keys()),
            "planners": list(PLANNER_MAP.keys()),
            "tools": TOOL_CHOICES,
        },
    )


@app.get("/api/defaults")
def api_defaults():
    return {
        "backend": "lm_studio",
        "model": "local-model",
        "base_url": "http://localhost:1234/v1",
        "planner": "react",
        "tools": ["web_search", "fetch", "calculator"],
        "max_iterations": 10,
        "temperature": 0.7,
        "max_tokens": 2048,
        "allowed_dirs": ".",
        "search_provider": "auto",
        "search_cse_id": "",
    }


@app.post("/api/run")
def run_agent(config: AgentConfig):
    if not config.task.strip():
        raise HTTPException(status_code=400, detail="Task is required.")
    if config.api_key or config.search_cse_id:
        raise HTTPException(status_code=400, detail="Save credentials using the credential manager first.")
    if "python_repl" in config.tools:
        raise HTTPException(status_code=400, detail="Python execution is disabled in the credential-enabled dashboard.")
    if config.planner not in PLANNER_MAP:
        raise HTTPException(status_code=400, detail="Unsupported planner.")

    try:
        backend = _build_backend(config)
        planner_cls = PLANNER_MAP.get(config.planner, ReActPlanner)
        planner = planner_cls(backend=backend)

        registry = ToolRegistry()
        tool_descriptions = []
        for tool_name in config.tools:
            if tool_name not in TOOL_CHOICES:
                continue
            tool = _tool_factory(tool_name, config)
            registry.register(tool)
            tool_descriptions.append(f"{tool.name}: {tool.description}")

        planner.tool_descriptions = "\n".join(tool_descriptions) if tool_descriptions else "No tools available."
        memory = MemoryManager()
        session_id = uuid.uuid4().hex
        tracer = Tracer(trace_dir=str(ROOT / "traces"), session_id=session_id)
        agent = Agent(
            backend=backend,
            planner=planner,
            tool_registry=registry,
            memory_manager=memory,
            tracer=tracer,
            max_iterations=config.max_iterations,
        )

        result = agent.run(config.task)
        trace_path = tracer.save()
        return {
            "status": "success",
            "result": result,
            "trace_path": trace_path,
            "session_id": session_id,
        }
    except Exception:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Agent execution failed. Check backend settings and provider availability.",
            },
        )


@app.get("/api/models")
def api_models(backend: str = "lm_studio", base_url: str = ""):
    fallback = FALLBACK_MODELS.get(backend, [])
    try:
        models = _fetch_models(backend, base_url, "")
    except Exception:
        return {
            "status": "error",
            "source": "fallback",
            "models": fallback,
            "message": f"Could not reach {backend}. Check provider settings or use a model name manually.",
        }

    if not models:
        return {
            "status": "empty",
            "source": "fallback",
            "models": fallback,
            "message": f"{backend} returned no models. Showing known names instead.",
        }

    return {
        "status": "ok",
        "source": "live",
        "models": models,
        "message": f"Loaded {len(models)} model(s) from {backend}.",
    }


@app.get("/api/keys")
def api_keys():
    result = {}
    for name in MANAGED_KEYS:
        try:
            encrypted = bool(credentials.store.get(name))
            available = True
        except CredentialError:
            encrypted, available = False, False
        legacy = bool(os.getenv(name) or _read_env_file().get(name))
        result[name] = {"set": encrypted or legacy, "encrypted": encrypted,
                        "legacy": legacy, "storage_available": available}
    return result


class KeyPayload(BaseModel):
    name: str
    value: str = ""

    model_config = {"extra": "ignore"}


@app.post("/api/save-key")
def save_key(payload: KeyPayload):
    if payload.name not in MANAGED_KEYS:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Unknown credential name."},
        )

    value = payload.value.strip()
    try:
        if value:
            credentials.store.set(payload.name, value)
        else:
            credentials.store.delete(payload.name)
        # Remove duplicate legacy entries only after a verified encrypted save.
        _write_env_file({payload.name: None})
        os.environ.pop(payload.name, None)
    except CredentialError:
        return JSONResponse(status_code=503, content={"status": "error", "message": "Encrypted credential storage is unavailable; no plaintext fallback was written."})
    return {"status": "saved", "message": "Credential saved in encrypted OS storage." if value else "Credential removed."}


@app.post("/api/migrate-keys")
def migrate_keys():
    legacy = _read_env_file()
    migrated = []
    try:
        for name in MANAGED_KEYS:
            value = legacy.get(name)
            if value:
                # Preserve a newer key already saved in native storage.
                if not credentials.store.get(name):
                    credentials.store.set(name, value)
                migrated.append(name)
        _write_env_file({name: None for name in migrated})
        for name in migrated:
            os.environ.pop(name, None)
    except CredentialError:
        return JSONResponse(status_code=503, content={"message": "Migration incomplete. Legacy entries were retained; encrypted storage must be available."})
    return {"status": "saved", "migrated": migrated, "message": "Legacy file credentials migrated. Remove any backups or synced historical copies separately."}


@app.post("/api/save-config")
async def save_config(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Invalid JSON payload."},
        )

    if not isinstance(payload, dict):
        return JSONResponse(status_code=400, content={"message": "Expected a JSON object."})
    # Export only known non-secret configuration, never arbitrary nested input.
    allowed = set(AgentConfig.model_fields) - {"api_key", "search_cse_id", "task"}
    payload = {key: value for key, value in payload.items() if key in allowed}
    try:
        payload = AgentConfig.model_validate(payload).model_dump(exclude={"api_key", "search_cse_id", "task"})
    except ValidationError:
        return JSONResponse(status_code=422, content={"message": "Invalid configuration fields."})
    payload = redact(payload)
    config_dir = ROOT / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    output_path = config_dir / "web_agent_config.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "status": "saved",
        "path": str(output_path),
        "message": "Configuration saved. Credentials are stored separately in encrypted OS storage.",
    }


@app.post("/api/save-env")
async def save_env(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Invalid JSON payload."},
        )

    if not isinstance(payload, dict):
        return JSONResponse(status_code=400, content={"message": "Expected a JSON object."})
    try:
        payload = AgentConfig.model_validate(payload).model_dump()
    except ValidationError:
        return JSONResponse(status_code=422, content={"message": "Invalid settings fields."})
    backend = str(payload.get("backend", "lm_studio"))
    base_url = str(payload.get("base_url", "http://localhost:1234/v1"))
    model_name = str(payload.get("model", "local-model"))

    updates: dict[str, str | None] = {
        "DEFAULT_BACKEND": backend,
        "LM_STUDIO_URL": base_url if backend == "lm_studio" else "http://localhost:1234/v1",
        "LM_STUDIO_MODEL": model_name if backend == "lm_studio" else "local-model",
        "OLLAMA_BASE_URL": base_url if backend == "ollama" else "http://localhost:11434",
        "OLLAMA_MODEL": model_name if backend == "ollama" else "llama3.1:8b",
        "OPENAI_MODEL": model_name if backend == "openai" else "gpt-4o-mini",
        "OPENROUTER_BASE_URL": base_url if backend == "openrouter" else "https://openrouter.ai/api/v1",
        "OPENROUTER_MODEL": model_name if backend == "openrouter" else "openai/gpt-4o-mini",
        "ANTHROPIC_MODEL": model_name if backend == "anthropic" else "claude-3-5-sonnet-20241022",
        "GROQ_MODEL": model_name if backend == "groq" else "llama-3.3-70b-versatile",
        "TOGETHER_MODEL": model_name if backend == "together" else "meta-llama/Llama-3-70b-chat-hf",
        "LM_STUDIO_TEMPERATURE": str(payload.get("temperature", 0.7)),
        "LM_STUDIO_MAX_TOKENS": str(payload.get("max_tokens", 2048)),
        "TOOLS_ENABLED": ",".join(payload.get("tools", ["web_search", "fetch", "calculator"])),
        "WEB_SEARCH_PROVIDER": str(payload.get("search_provider", "auto")),
        "ALLOWED_DIRS": str(payload.get("allowed_dirs", ".")),
        "MAX_ITERATIONS": str(payload.get("max_iterations", 10)),
    }

    # This endpoint writes non-secret settings only. Key saving is separate.
    updates = redact(updates)

    _write_env_file(updates)
    return {
        "status": "saved",
        "path": str(ENV_PATH),
        "message": "Settings merged into .env. Existing values were preserved.",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("debugging.dashboard.server:app", host="127.0.0.1", port=8765, reload=False, access_log=False)
