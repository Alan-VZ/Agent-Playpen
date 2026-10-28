import socket

import pytest


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch, tmp_path):
    """Never use saved credentials, live services, or project runtime files."""
    monkeypatch.chdir(tmp_path)
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
