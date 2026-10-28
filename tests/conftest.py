import socket

import pytest
from config import credentials


class MemoryKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, name):
        return self.values.get((service, name))

    def set_password(self, service, name, value):
        self.values[service, name] = value

    def delete_password(self, service, name):
        self.values.pop((service, name), None)


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch, tmp_path):
    """Never use saved credentials, live services, or project runtime files."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(credentials, "store", credentials.CredentialStore(MemoryKeyring()))
    monkeypatch.setattr(credentials, "LEGACY_ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(credentials, "_known_secrets", set())
    for name in credentials.MANAGED_KEYS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MEMORY_ENABLED_STORES", "working,conversation")

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guard(original):
        def connect(sock, address):
            # Windows asyncio uses a loopback socket pair internally.
            if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
                return original(sock, address)
            raise AssertionError("External network access is disabled in tests")
        return connect

    monkeypatch.setattr(socket.socket, "connect", guard(original_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guard(original_connect_ex))
