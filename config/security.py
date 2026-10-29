"""Boundaries for agent-facing filesystem access and cloud credential routing."""

from pathlib import Path
from urllib.parse import urlsplit


def check_sensitive_path(path: Path) -> None:
    resolved = path.resolve()
    for part in (*path.parts, *resolved.parts):
        name = part.lower()
        if (name.startswith(".env") and name != ".env.example") or name in {
            ".ssh", ".aws", ".azure", ".gnupg", ".codex", ".git", ".venv", ".venv-test",
            "credentials", "vault", "keyrings", "secrets",
        }:
            raise PermissionError("Agent file tools cannot access credential or private configuration paths.")
        if Path(name).stem in {"credentials", "secrets", "vault", "keyring"} or Path(name).suffix in {".key", ".pem", ".pfx", ".p12"}:
            raise PermissionError("Agent file tools cannot access credential material.")


def azure_endpoint(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname
            or not parsed.hostname.endswith(".openai.azure.com")
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("Use an HTTPS Azure endpoint under *.openai.azure.com.")
    return value.rstrip("/")


def openrouter_endpoint(value: str) -> str:
    if value.rstrip("/") != "https://openrouter.ai/api/v1":
        raise ValueError("OpenRouter credentials can only be sent to https://openrouter.ai/api/v1.")
    return "https://openrouter.ai/api/v1"
