"""Explicit local LM Studio model management; discovery never changes loaded models."""
import json
import threading
import time
from urllib.parse import urlsplit

import requests


class ModelManagementError(RuntimeError):
    pass


SWITCH_LOCK = threading.Lock()


def server_root(base_url):
    try:
        parsed = urlsplit(base_url or "http://localhost:1234/v1")
        if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path.rstrip("/") not in {"", "/v1"}):
            raise ValueError()
        port = parsed.port
        host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
        return f"http://{host}" + (f":{port}" if port else "")
    except ValueError:
        raise ModelManagementError("Model loading requires an HTTP loopback LM Studio URL without credentials or query parameters.") from None


def request_json(session, method, url, **kwargs):
    try:
        with session.request(method, url, timeout=120 if method == "POST" else 10,
                             allow_redirects=False, stream=True, **kwargs) as response:
            if response.status_code in {401, 403}:
                raise ModelManagementError("LM Studio requires local API authentication or denied this operation. No cloud API key was forwarded.")
            if response.status_code == 404:
                raise ModelManagementError("LM Studio's native model-management API is unavailable. Use LM Studio 0.4+ or load the model in LM Studio itself.")
            content = bytearray()
            for chunk in response.iter_content(16384):
                content.extend(chunk)
                if len(content) > 2 * 1024 * 1024:
                    raise ModelManagementError("LM Studio's response exceeded the model-management size limit.")
            data = json.loads(content)
            error = data.get("error") if isinstance(data, dict) else None
            if isinstance(error, dict) and error.get("type") == "model_load_failed":
                raise ModelManagementError("LM Studio could not load the selected model. Its engine reported model_load_failed; check free GPU memory and the model's GPU offload/context settings. No automatic load retry was made.")
            if not 200 <= response.status_code < 300:
                raise ModelManagementError(f"LM Studio returned HTTP {response.status_code}. Check its model-load log and available memory. No automatic load retry was made.")
            if not isinstance(data, dict) or error:
                raise ModelManagementError("LM Studio did not confirm the model operation. Check its local log.")
            return data
    except requests.Timeout:
        raise ModelManagementError("LM Studio timed out. Loading may still be in progress; check status before trying again. No automatic load retry was made.") from None
    except requests.RequestException:
        raise ModelManagementError("Cannot reach LM Studio. Start its local API server and check the Base URL.") from None
    except (ValueError, TypeError):
        raise ModelManagementError("LM Studio returned an invalid model-management response.") from None


def catalog(session, root):
    data = request_json(session, "GET", root + "/api/v1/models")
    models = data.get("models")
    if not isinstance(models, list):
        raise ModelManagementError("LM Studio returned an unexpected native model catalog.")
    return [m for m in models if isinstance(m, dict) and isinstance(m.get("key"), str)]


def find_model(models, name):
    if not name or name == "local-model":
        raise ModelManagementError("Choose an explicit model ID from Refresh model list; local-model is only a placeholder.")
    matches = [m for m in models if m["key"] == name or any(isinstance(i, dict) and i.get("id") == name for i in m.get("loaded_instances", []))]
    if len(matches) != 1:
        raise ModelManagementError("The selected model was not uniquely found in LM Studio. Refresh the model list and choose its exact ID.")
    if matches[0].get("type") != "llm":
        raise ModelManagementError("Choose a text-generation model; embedding models cannot run agent tasks.")
    return matches[0]


def describe(model, instance_id=None):
    ids = [i["id"] for i in model.get("loaded_instances", []) if isinstance(i, dict) and isinstance(i.get("id"), str)]
    return {"key": model["key"], "loaded": bool(ids), "instance_ids": ids,
            "model": instance_id if instance_id in ids else ids[0] if ids else model["key"]}


def other_instances(models, selected_key):
    return list(dict.fromkeys(instance["id"] for model in models
                              if model["key"] != selected_key and model.get("type") in {"llm", "decision"}
                              for instance in model.get("loaded_instances", [])
                              if isinstance(instance, dict) and isinstance(instance.get("id"), str)))


def unload_previous(session, root, models, selected_key):
    """Follow ComfyUI's release-before-allocation lifecycle through LM Studio's API."""
    previous = other_instances(models, selected_key)
    if not previous:
        return []
    unloaded = []
    for instance in previous:
        try:
            result = request_json(session, "POST", root + "/api/v1/models/unload", json={"instance_id": instance})
            if result.get("instance_id") != instance:
                raise ModelManagementError("LM Studio did not acknowledge the exact instance being unloaded.")
            unloaded.append(instance)
        except ModelManagementError as exc:
            raise ModelManagementError(f"Stopped while unloading previous models ({len(unloaded)}/{len(previous)} acknowledged). The new model was not loaded. {exc}") from None
    # LM Studio owns the CUDA allocations. Waiting for its instance removal is
    # meaningful; empty_cache() in this separate Python process would not free them.
    for poll in range(6):
        remaining = other_instances(catalog(session, root), selected_key)
        if not remaining:
            return unloaded
        if any(instance not in previous for instance in remaining):
            raise ModelManagementError("Another model appeared while switching. The new model was not loaded; wait for other model operations to finish.")
        if poll < 5:
            time.sleep(.2)
    raise ModelManagementError("Previous model instances are still listed as loaded after unload requests. The new model was not loaded; check LM Studio.")


def manage(base_url, model, load=False, replace_loaded=True):
    if not load:
        return _manage(base_url, model, False, False)
    if not SWITCH_LOCK.acquire(blocking=False):
        raise ModelManagementError("Another model switch is already in progress. Check status and wait before loading again.")
    try:
        return _manage(base_url, model, True, replace_loaded)
    finally:
        SWITCH_LOCK.release()


def _manage(base_url, model, load, replace_loaded):
    root = server_root(base_url)
    with requests.Session() as session:
        session.trust_env = False
        models = catalog(session, root)
        selected = find_model(models, model)
        result = describe(selected, model)
        unloaded = unload_previous(session, root, models, selected["key"]) if load and replace_loaded else []
        if load and not result["loaded"]:
            try:
                response = request_json(session, "POST", root + "/api/v1/models/load", json={"model": selected["key"]})
            except ModelManagementError as exc:
                prefix = f"Previous model instances unloaded: {len(unloaded)}. " if unloaded else ""
                raise ModelManagementError(prefix + str(exc)) from None
            instance = response.get("instance_id")
            if response.get("status") != "loaded" or not isinstance(instance, str):
                raise ModelManagementError("LM Studio did not confirm a loaded model instance. Check status in LM Studio.")
            verified = find_model(catalog(session, root), selected["key"])
            result = describe(verified, instance)
            if instance not in result["instance_ids"]:
                raise ModelManagementError("The load request returned, but its model instance is not listed as loaded. Check LM Studio before running.")
        elif load and unloaded:
            result = describe(find_model(catalog(session, root), selected["key"]), model)
            if not result["loaded"]:
                raise ModelManagementError("The selected model is no longer loaded after switching. Check LM Studio.")
        result["unloaded_instances"] = unloaded
        result["status"] = "loaded" if result["loaded"] else "not_loaded"
        result["message"] = ((f"Unloaded {len(unloaded)} previous model instance(s). " if unloaded else "") + f"Loaded in LM Studio: {result['model']}." if result["loaded"] else
                             "Available on disk, but not loaded in LM Studio. Click Load selected model in LM Studio.")
        return result
