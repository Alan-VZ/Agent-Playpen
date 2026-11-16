"""One selection lifecycle for model providers, with leases for local engines."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time

import requests

from debugging.dashboard import local_models

LOCAL = {"lm_studio", "ollama"}
_LOCKS = {}
_LOCK = threading.Lock()
_LOCK_DIRECTORY = Path(tempfile.gettempdir()) / "agent-playpen-model-leases"


class EngineLock:
    """OS-backed lease shared by dashboard threads and spawned benchmark workers.

    The OS releases the lock if a bounded worker is terminated. The file contains
    one marker byte, never model configuration or credentials.
    """

    def __init__(self, key):
        self.path = _LOCK_DIRECTORY / (
            hashlib.sha256(repr(key).encode()).hexdigest() + ".lock"
        )
        self.thread = threading.Lock()
        self.handle = None

    def acquire(self, blocking=True, timeout=-1):
        end = time.monotonic() + timeout if timeout >= 0 else None
        while True:
            if self.thread.acquire(blocking=False):
                handle = None
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    handle = self.path.open("a+b")
                    if self.path.stat().st_size == 0:
                        handle.write(b"0")
                        handle.flush()
                    handle.seek(0)
                    try:
                        if os.name == "nt":
                            import msvcrt

                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl

                            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except (BlockingIOError, PermissionError):
                        handle.close()
                        self.thread.release()
                    except OSError as exc:
                        # Windows reports a contended byte-range lock as EACCES.
                        if exc.errno not in {11, 13, 36}:
                            raise
                        handle.close()
                        self.thread.release()
                    else:
                        self.handle = handle
                        return True
                except Exception:
                    if handle is not None:
                        handle.close()
                    self.thread.release()
                    raise
            if not blocking or (end is not None and time.monotonic() >= end):
                return False
            time.sleep(0.02)

    def release(self):
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None
            self.thread.release()


def engine_key(backend, base_url=None):
    if backend not in LOCAL:
        return None
    root = local_models.server_root(
        base_url
        or (
            "http://localhost:11434/v1"
            if backend == "ollama"
            else "http://localhost:1234/v1"
        )
    )
    return backend, root.replace("localhost", "127.0.0.1").replace("[::1]", "127.0.0.1")


def engine_lock(backend, base_url=None):
    key = engine_key(backend, base_url)
    with _LOCK:
        return _LOCKS.setdefault(key, EngineLock(key))


def _ollama_request(session, root, path, payload=None):
    try:
        with session.request(
            "POST" if payload is not None else "GET",
            root + path,
            json=payload,
            timeout=120 if payload is not None else 10,
            allow_redirects=False,
            stream=True,
        ) as response:
            if not 200 <= response.status_code < 300:
                raise local_models.ModelManagementError(
                    f"Ollama returned HTTP {response.status_code}. Check its local server and installed models."
                )
            body = bytearray()
            for chunk in response.iter_content(16384):
                body.extend(chunk)
                if len(body) > 2 * 1024 * 1024:
                    raise local_models.ModelManagementError(
                        "Ollama returned too much model data."
                    )
            result = json.loads(body)
            if not isinstance(result, dict) or result.get("error"):
                raise local_models.ModelManagementError(
                    "Ollama could not complete the model operation. Check its local log."
                )
            return result
    except (requests.RequestException, ValueError):
        raise local_models.ModelManagementError(
            "Cannot complete the Ollama model request. Check its server; no automatic load retry was made."
        ) from None


def local_state(backend, base_url=None):
    _, root = engine_key(backend, base_url)
    with requests.Session() as session:
        session.trust_env = False
        if backend == "lm_studio":
            models = local_models.catalog(session, root)
            entries = []
            for model in models:
                if model.get("type") != "llm":
                    continue
                instances = [
                    i["id"]
                    for i in model.get("loaded_instances", [])
                    if isinstance(i, dict) and isinstance(i.get("id"), str)
                ]
                entries.append(
                    {
                        "id": model["key"],
                        "loaded": bool(instances),
                        "instances": instances,
                    }
                )
        else:
            available = _ollama_request(session, root, "/api/tags").get("models", [])
            running = _ollama_request(session, root, "/api/ps").get("models", [])
            active = {
                m.get("name") or m.get("model") for m in running if isinstance(m, dict)
            }
            entries = [
                {
                    "id": m.get("name") or m.get("model"),
                    "loaded": (m.get("name") or m.get("model")) in active,
                    "instances": [m.get("name") or m.get("model")]
                    if (m.get("name") or m.get("model")) in active
                    else [],
                }
                for m in available
                if isinstance(m, dict)
                and isinstance(m.get("name") or m.get("model"), str)
            ]
    return {
        "backend": backend,
        "models": entries,
        "active_models": [
            instance for model in entries for instance in model["instances"]
        ],
        "source": "live",
    }


def _activate(backend, model, base_url=None):
    if not model.strip() or model == "local-model":
        raise local_models.ModelManagementError("Choose a model before running.")
    if backend == "lm_studio":
        return local_models.manage(
            base_url or "http://localhost:1234/v1", model, load=True
        )
    if backend != "ollama":
        return {
            "model": model,
            "status": "selected",
            "loaded": False,
            "message": "Selected for requests.",
        }
    state = local_state(backend, base_url)
    if model not in {m["id"] for m in state["models"]}:
        raise local_models.ModelManagementError(
            "Choose an installed Ollama model from the list."
        )
    _, root = engine_key(backend, base_url)
    with requests.Session() as session:
        session.trust_env = False
        for previous in state["active_models"]:
            if previous != model:
                _ollama_request(
                    session,
                    root,
                    "/api/generate",
                    {"model": previous, "keep_alive": 0, "stream": False},
                )
        remaining = local_state(backend, base_url)["active_models"]
        if any(name != model for name in remaining):
            raise local_models.ModelManagementError(
                "Ollama has not released the previous model. Selection was not changed."
            )
        if model not in remaining:
            _ollama_request(
                session,
                root,
                "/api/generate",
                {"model": model, "keep_alive": "10m", "stream": False},
            )
    if model not in local_state(backend, base_url)["active_models"]:
        raise local_models.ModelManagementError(
            "Ollama did not confirm the selected model as loaded."
        )
    return {"model": model, "loaded": True, "status": "loaded", "message": "Ready."}


def select_model(backend, model, base_url=None):
    if backend not in LOCAL:
        return _activate(backend, model, base_url)
    lock = engine_lock(backend, base_url)
    if not lock.acquire(blocking=False):
        raise local_models.ModelManagementError(
            "This local server is in use. Selection was not changed; wait for the active model to finish."
        )
    try:
        return _activate(backend, model, base_url)
    finally:
        lock.release()


@contextmanager
def model_lease(
    backend, model, base_url=None, deadline=None, stopped=None, on_status=None
):
    """Keep a local engine assigned for an entire agent run, not one HTTP call."""
    if backend not in LOCAL:
        yield model
        return
    lock = engine_lock(backend, base_url)
    while not lock.acquire(timeout=0.1):
        if stopped and stopped.is_set():
            raise RuntimeError("Run stopped while waiting for a local model.")
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("Local model queue deadline exceeded.")
    try:
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("Local model queue deadline exceeded.")
        if stopped and stopped.is_set():
            raise RuntimeError("Run stopped before preparing the local model.")
        if on_status:
            on_status(
                "Preparing "
                + model
                + ". Other slots sharing this server wait their turn."
            )
        selected = _activate(backend, model, base_url)
        yield selected["model"]
    finally:
        lock.release()
