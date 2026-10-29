"""Native OS credential storage. Never fall back to a plaintext keyring."""

import getpass
import os
from pathlib import Path
import sys
import threading

from dotenv import dotenv_values

SERVICE = "Agent Playpen"
BACKEND_KEYS = {
    "openai": "OPENAI_API_KEY", "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY", "groq": "GROQ_API_KEY",
    "together": "TOGETHER_API_KEY", "azure_openai": "AZURE_OPENAI_KEY",
}
SEARCH_KEYS = {
    "tavily": "TAVILY_API_KEY", "serpapi": "SERPAPI_API_KEY", "google": "GOOGLE_API_KEY",
    "serper": "SERPER_API_KEY", "brave": "BRAVE_API_KEY", "exa": "EXA_API_KEY",
    "firecrawl": "FIRECRAWL_API_KEY", "openwebninja": "OPENWEBNINJA_API_KEY",
}
MANAGED_KEYS = frozenset([*BACKEND_KEYS.values(), *SEARCH_KEYS.values(), "GOOGLE_CSE_ID"])
LEGACY_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
_known_secrets: set[str] = set()
_lock = threading.RLock()


class CredentialError(RuntimeError):
    pass


def remember_secret(value: str) -> str:
    if value:
        with _lock:
            _known_secrets.add(value)
    return value


def redact(value):
    """Remove known credential values from outbound text and trace content."""
    if isinstance(value, str):
        with _lock:
            for secret in sorted(_known_secrets, key=len, reverse=True):
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, dict):
        return {redact(k): redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


class CredentialStore:
    """Use only the explicitly selected native encrypted credential service."""

    def __init__(self, backend=None):
        self._backend = backend

    def _native(self):
        if self._backend is None:
            try:
                if sys.platform == "win32":
                    from keyring.backends.Windows import WinVaultKeyring
                    self._backend = WinVaultKeyring()
                elif sys.platform == "darwin":
                    from keyring.backends.macOS import Keyring
                    self._backend = Keyring()
                else:
                    from keyring.backends.SecretService import Keyring
                    self._backend = Keyring()
            except Exception:
                raise CredentialError("Native encrypted credential storage is unavailable. No plaintext fallback is used.") from None
        return self._backend

    @staticmethod
    def _validate(name):
        if name not in MANAGED_KEYS:
            raise CredentialError("Unknown credential name.")

    def get(self, name: str) -> str:
        self._validate(name)
        try:
            return remember_secret(self._native().get_password(SERVICE, name) or "")
        except CredentialError:
            raise
        except Exception:
            raise CredentialError("Unable to read the native credential store.") from None

    def set(self, name: str, value: str) -> None:
        self._validate(name)
        if not value or any(c in value for c in "\r\n\x00"):
            raise CredentialError("Credentials must be nonempty single-line values.")
        remember_secret(value)
        with _lock:
            try:
                self._native().set_password(SERVICE, name, value)
                if self.get(name) != value:
                    raise CredentialError("Credential save verification failed.")
            except CredentialError:
                raise
            except Exception:
                raise CredentialError("Unable to save to the native encrypted credential store.") from None

    def delete(self, name: str) -> None:
        self._validate(name)
        with _lock:
            try:
                if self.get(name):
                    self._native().delete_password(SERVICE, name)
            except CredentialError:
                raise
            except Exception:
                raise CredentialError("Unable to remove the encrypted credential.") from None


store = CredentialStore()


def get_credential(name: str, supplied: str = "") -> str:
    """Resolve explicit input, native storage, then legacy env/file input."""
    CredentialStore._validate(name)
    if supplied:
        return remember_secret(supplied)
    try:
        value = store.get(name)
    except CredentialError:
        # Existing env credentials can still be used; saves always fail closed.
        value = ""
    if not value:
        value = os.getenv(name, "")
    if not value and LEGACY_ENV_PATH.is_file():
        value = dotenv_values(LEGACY_ENV_PATH, interpolate=False, encoding="utf-8-sig").get(name) or ""
    return remember_secret(value)


def require_credential(name: str, supplied: str = "") -> str:
    value = get_credential(name, supplied)
    if not value:
        raise CredentialError(f"Save {name} in the credential manager before using this backend.")
    return value


def subprocess_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in MANAGED_KEYS}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Manage encrypted Agent Playpen credentials; values are never printed.")
    parser.add_argument("action", choices=["set", "delete", "status"])
    parser.add_argument("name", choices=sorted(MANAGED_KEYS))
    args = parser.parse_args()
    try:
        if args.action == "set":
            store.set(args.name, getpass.getpass("API key / credential (hidden): ").strip())
            print("Credential saved in native encrypted storage.")
        elif args.action == "delete":
            store.delete(args.name)
            print("Encrypted credential removed. Remove any legacy environment copy separately.")
        else:
            print("Encrypted credential is set." if store.get(args.name) else "Encrypted credential is not set.")
    except CredentialError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
