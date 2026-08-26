from __future__ import annotations

import json
import os
import traceback
import uuid
from pathlib import Path

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from backends.backend_factory import BackendFactory
from core.agent import Agent
from debugging.tracer import Tracer
from memory.memory_manager import MemoryManager
from planner.cot_planner import CoTPlanner
from planner.react_planner import ReActPlanner
from planner.tree_planner import TreePlanner
from tools.packs.code.python_repl import PythonReplTool
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

BACKEND_KEY_VAR = {
    "openai": "OPENAI_API_KEY",
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
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def _write_env_file(updates: dict[str, str | None]) -> None:
    """
    Merge updates into .env, preserving every unrelated line, comment and
    blank line. A value of None deletes that entry.
    """
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    pending = dict(updates)
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(line)
            continue
        key = stripped.partition("=")[0].strip()
        if key in pending:
            value = pending.pop(key)
            if value is not None:
                output.append(f"{key}={value}")
        else:
            output.append(line)

    for key, value in pending.items():
        if value is not None:
            output.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(output).rstrip("\n") + "\n", encoding="utf-8")


def _load_env_into_process() -> None:
    """Make saved .env values visible to os.getenv without python-dotenv."""
    for key, value in _read_env_file().items():
        os.environ.setdefault(key, value)


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}...{value[-4:]}"


_load_env_into_process()

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app = FastAPI(title="Agent Playpen Web Wrapper", version="1.0.0")

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
    "python_repl",
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
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return sorted(m["id"] for m in response.json().get("data", []))

    if backend == "ollama":
        url = (base_url or "http://localhost:11434").rstrip("/") + "/api/tags"
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return sorted(m["name"] for m in response.json().get("models", []))

    if backend in {"openai", "groq", "together"}:
        endpoints = {
            "openai": "https://api.openai.com/v1/models",
            "groq": "https://api.groq.com/openai/v1/models",
            "together": "https://api.together.xyz/v1/models",
        }
        key = _require_key(api_key or os.getenv(BACKEND_KEY_VAR[backend], ""), backend)
        response = requests.get(
            endpoints[backend],
            headers={"Authorization": "Bearer " + key},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        entries = payload.get("data", payload) if isinstance(payload, dict) else payload
        return sorted(e["id"] for e in entries if isinstance(e, dict) and e.get("id"))

    if backend == "anthropic":
        key = _require_key(api_key or os.getenv("ANTHROPIC_API_KEY", ""), backend)
        response = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            timeout=timeout,
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
    max_tokens: int = 2048
    planner: str = "react"
    tools: list[str] = Field(default_factory=lambda: ["web_search", "fetch", "calculator"])
    task: str = ""
    max_iterations: int = 10
    allowed_dirs: str = "."
    search_provider: str = "auto"
    search_cse_id: str = ""

    model_config = {"extra": "ignore"}


def _tool_factory(name: str, config: AgentConfig):
    dirs = [d.strip() for d in config.allowed_dirs.split(",") if d.strip()] or ["."]

    if name == "web_search":
        key_var = SEARCH_KEY_VAR.get(config.search_provider)
        search_key = (os.getenv(key_var, "") if key_var else "") or config.api_key
        cse_var = SEARCH_EXTRA_VAR.get(config.search_provider)
        search_cse_id = (os.getenv(cse_var, "") if cse_var else "") or config.search_cse_id
        return WebSearchTool(provider=config.search_provider, api_key=search_key or None, cse_id=search_cse_id or None)
    if name == "fetch":
        return FetchTool()
    if name == "read_file":
        return ReadFileTool(allowed_dirs=dirs)
    if name == "write_file":
        return WriteFileTool(allowed_dirs=dirs)
    if name == "python_repl":
        return PythonReplTool()
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
        kwargs["api_key"] = config.api_key or os.getenv("OPENAI_API_KEY", "")
        kwargs["org_id"] = os.getenv("OPENAI_ORG_ID")
        backend = BackendFactory.create("openai", **kwargs)
    elif config.backend == "anthropic":
        kwargs["api_key"] = config.api_key or os.getenv("ANTHROPIC_API_KEY", "")
        backend = BackendFactory.create("anthropic", **kwargs)
    elif config.backend == "azure_openai":
        kwargs["api_key"] = config.api_key or os.getenv("AZURE_OPENAI_KEY", "")
        kwargs["endpoint"] = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        kwargs["deployment"] = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        kwargs["api_version"] = os.getenv("AZURE_OPENAI_API_VERSION", "")
        backend = BackendFactory.create("azure_openai", **kwargs)
    elif config.backend == "groq":
        kwargs["api_key"] = config.api_key or os.getenv("GROQ_API_KEY", "")
        backend = BackendFactory.create("groq", **kwargs)
    elif config.backend == "together":
        kwargs["api_key"] = config.api_key or os.getenv("TOGETHER_API_KEY", "")
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
        raise ValueError("Task is required.")

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
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        )


@app.get("/api/models")
def api_models(backend: str = "lm_studio", base_url: str = "", api_key: str = ""):
    fallback = FALLBACK_MODELS.get(backend, [])
    try:
        models = _fetch_models(backend, base_url, api_key)
    except Exception as exc:
        return {
            "status": "error",
            "source": "fallback",
            "models": fallback,
            "message": f"Could not reach {backend}: {exc}",
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
    stored = _read_env_file()
    result = {}
    for name in MANAGED_KEYS:
        value = stored.get(name) or os.getenv(name, "")
        result[name] = {"set": bool(value), "hint": _mask(value)}
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
            content={"status": "error", "message": f"Unknown key name: {payload.name}"},
        )

    value = payload.value.strip()
    if value:
        _write_env_file({payload.name: value})
        os.environ[payload.name] = value
        message = f"{payload.name} saved. It will be reused automatically."
    else:
        _write_env_file({payload.name: None})
        os.environ.pop(payload.name, None)
        message = f"{payload.name} removed."

    return {"status": "saved", "message": message, "path": str(ENV_PATH)}


@app.post("/api/save-config")
async def save_config(request: Request):
    try:
        payload = await request.json()
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": f"Invalid JSON payload: {exc}"},
        )

    payload.pop("api_key", None)
    payload.pop("search_cse_id", None)
    config_dir = ROOT / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    output_path = config_dir / "web_agent_config.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "status": "saved",
        "path": str(output_path),
        "message": "Configuration saved. API keys are kept in .env, not here.",
    }


@app.post("/api/save-env")
async def save_env(request: Request):
    try:
        payload = await request.json()
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": f"Invalid JSON payload: {exc}"},
        )

    updates: dict[str, str | None] = {
        "DEFAULT_BACKEND": str(payload.get("backend", "lm_studio")),
        "LM_STUDIO_URL": str(payload.get("base_url", "http://localhost:1234/v1")),
        "LM_STUDIO_MODEL": str(payload.get("model", "local-model")),
        "LM_STUDIO_TEMPERATURE": str(payload.get("temperature", 0.7)),
        "LM_STUDIO_MAX_TOKENS": str(payload.get("max_tokens", 2048)),
        "TOOLS_ENABLED": ",".join(payload.get("tools", ["web_search", "fetch", "calculator"])),
        "WEB_SEARCH_PROVIDER": str(payload.get("search_provider", "auto")),
        "ALLOWED_DIRS": str(payload.get("allowed_dirs", ".")),
        "MAX_ITERATIONS": str(payload.get("max_iterations", 10)),
    }

    api_key = str(payload.get("api_key") or "").strip()
    if api_key:
        backend = str(payload.get("backend", ""))
        key_var = BACKEND_KEY_VAR.get(backend)
        search_provider = str(payload.get("search_provider", ""))
        search_key_var = SEARCH_KEY_VAR.get(search_provider)
        if key_var:
            updates[key_var] = api_key
            os.environ[key_var] = api_key
        elif search_key_var:
            updates[search_key_var] = api_key
            os.environ[search_key_var] = api_key

    search_cse_id = str(payload.get("search_cse_id") or "").strip()
    search_provider = str(payload.get("search_provider", ""))
    search_extra_var = SEARCH_EXTRA_VAR.get(search_provider)
    if search_cse_id and search_extra_var:
        updates[search_extra_var] = search_cse_id
        os.environ[search_extra_var] = search_cse_id

    _write_env_file(updates)
    return {
        "status": "saved",
        "path": str(ENV_PATH),
        "message": "Settings merged into .env. Existing values were preserved.",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("debugging.dashboard.server:app", host="0.0.0.0", port=8765, reload=False)
