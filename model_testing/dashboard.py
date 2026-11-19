"""Dashboard integration for MTT source/catalog/campaign/recommendation flows."""

from __future__ import annotations

import threading
import time
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from model_testing.store import MttStore
from model_testing.campaign import MttCampaignManager


class SourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal[
        "lm_studio",
        "ollama",
        "openai",
        "openrouter",
        "anthropic",
        "azure_openai",
        "groq",
        "together",
    ]
    name: str = Field(min_length=1, max_length=200)
    endpoint: str = Field(default="", max_length=500)
    account_alias: str = Field(default="", max_length=200)
    standing_policy: dict = Field(default_factory=dict)


class StandingPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    profile_id: Literal["diagnostics-v1", "diagnostics-screen-v1"] = "diagnostics-screen-v1"
    free_only: bool = True
    max_models_per_campaign: int = Field(default=10, ge=1, le=100)
    max_model_requests: int = Field(default=80, ge=1, le=100000)
    max_wall_seconds: int = Field(default=1200, ge=60, le=86400)
    refresh_interval_minutes: int = Field(default=1440, ge=60, le=525600)
    campaign_on_discovery: bool = False


class CampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1, max_length=64)
    model_ids: list[str] = Field(min_length=1, max_length=100)
    profile_id: Literal["diagnostics-v1", "diagnostics-screen-v1"] = "diagnostics-screen-v1"
    standing_policy_id: str = Field(default="", max_length=64)
    max_attempts: int = Field(default=24, ge=1, le=240)
    max_model_requests: int = Field(default=80, ge=1, le=100000)
    max_wall_seconds: int = Field(default=1200, ge=60, le=86400)
    max_tokens: int = Field(default=300000, ge=1000, le=10000000)
    cost_limit: float | None = Field(default=None, ge=0)
    case_timeout_seconds: float = Field(default=400, ge=1, le=1800)


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: Literal["diagnostics-v1", "diagnostics-screen-v1"] = "diagnostics-v1"
    free_only: bool = False
    deadline_seconds: int | None = Field(default=None, ge=1, le=1800)
    provider: str | None = Field(default=None, max_length=100)


MTT_STORE: MttStore | None = None
MTT_MANAGER: MttCampaignManager | None = None


def install(server):
    from debugging.dashboard import model_sources

    if getattr(server.app.state, "mtt_installed", False):
        return
    server.app.state.mtt_installed = True

    store = MttStore()
    evidence_root = store.path.parent / "evidence"
    manager = MttCampaignManager(store, evidence_root)
    manager.reconcile()
    global MTT_STORE, MTT_MANAGER
    MTT_STORE = store
    MTT_MANAGER = manager
    service_lock = threading.RLock()

    def normalize_discovery(provider: str, endpoint: str) -> dict:
        if provider in model_sources.LOCAL:
            try:
                state = model_sources.local_state(provider, endpoint)
                entries = [
                    {
                        "model_id": model["id"],
                        "display_name": model["id"],
                        "model_type": "llm",
                        "access_state": "account_or_local_ready",
                        "installed": bool(model["loaded"]),
                        "loaded": bool(model["loaded"]),
                    }
                    for model in state["models"]
                    if isinstance(model, dict) and model.get("id")
                ]
                return {
                    "status": "completed",
                    "source": "live",
                    "entries": entries,
                }
            except Exception as exc:
                return {
                    "status": "failed",
                    "source": "live",
                    "entries": [],
                    "error": str(exc)[:2000],
                }
        if provider == "azure_openai":
            return {
                "status": "configuration_required",
                "source": "manual",
                "entries": [],
                "error": "Azure deployment discovery requires the configured deployment name.",
            }
        try:
            api_key = ""
            key_name = server.BACKEND_KEY_VAR.get(provider)
            if key_name:
                api_key = server.get_credential(key_name)
            catalog = server._fetch_models(provider, endpoint, api_key)
            entries = []
            if hasattr(catalog, "data"):
                raw_entries = getattr(catalog, "data")
            elif isinstance(catalog, dict):
                raw_entries = catalog.get("data", [])
            elif isinstance(catalog, list):
                raw_entries = catalog
            else:
                raw_entries = []
            for entry in raw_entries:
                if hasattr(entry, "id"):
                    model_id = entry.id
                elif isinstance(entry, dict):
                    model_id = entry.get("id") or entry.get("name")
                elif isinstance(entry, str):
                    model_id = entry
                else:
                    model_id = None
                if not model_id:
                    continue
                entries.append(
                    {
                        "model_id": str(model_id),
                        "display_name": str(model_id),
                        "model_type": "llm",
                        "access_state": "catalog_verified",
                        "installed": False,
                        "loaded": False,
                    }
                )
            return {
                "status": "completed",
                "source": "live",
                "entries": entries,
            }
        except Exception as exc:
            return {
                "status": "failed",
                "source": "live",
                "entries": [],
                "error": str(exc)[:2000],
            }

    def standing_worker():
        while True:
            try:
                for source in store.list_sources():
                    policy = source.get("standing_policy") or {}
                    if not policy.get("enabled"):
                        continue
                    interval_minutes = int(
                        policy.get("refresh_interval_minutes", 1440)
                    )
                    due = True
                    last_refresh = source.get("last_refresh_at")
                    if last_refresh:
                        from datetime import datetime

                        try:
                            parsed = datetime.fromisoformat(last_refresh)
                            due = (
                                time.time() - parsed.timestamp()
                                >= max(60, interval_minutes * 60)
                            )
                        except (TypeError, ValueError):
                            due = True
                    if not due:
                        continue
                    if policy.get("free_only") and source["provider"] not in {
                        "lm_studio",
                        "ollama",
                    }:
                        continue
                    discovery = normalize_discovery(
                        source["provider"], source["endpoint"]
                    )
                    store.save_catalog(
                        source["id"],
                        discovery["entries"],
                        status=discovery["status"],
                        error=discovery.get("error", ""),
                    )
                    if not policy.get("campaign_on_discovery"):
                        continue
                    if discovery["status"] != "completed":
                        continue
                    from debugging.dashboard.experiments import JOBS

                    with service_lock:
                        if any(
                            job.get("status") == "running"
                            for job in JOBS.values()
                        ):
                            continue
                    catalog = store.list_catalog(
                        source["id"], include_unlisted=False
                    )
                    profile_id = policy.get("profile_id", "diagnostics-v1")
                    active_campaigns = [
                        campaign
                        for campaign in store.list_campaigns(limit=500)
                        if campaign["source_id"] == source["id"]
                        and campaign["status"] in {"queued", "running"}
                    ]
                    if active_campaigns:
                        continue
                    model_ids = []
                    for entry in catalog["entries"]:
                        model_id = entry["model_id"]
                        latest = store.latest_qualification(
                            profile_id,
                            source_id=source["id"],
                            model_id=model_id,
                        )
                        if latest:
                            valid_until = latest.get("valid_until")
                            if valid_until:
                                try:
                                    from datetime import datetime, timezone

                                    expires = datetime.fromisoformat(valid_until)
                                    if expires.tzinfo is None:
                                        expires = expires.replace(tzinfo=timezone.utc)
                                    if expires > datetime.now(timezone.utc):
                                        continue
                                except (TypeError, ValueError):
                                    pass
                        model_ids.append(model_id)
                        if len(model_ids) >= int(
                            policy.get("max_models_per_campaign", 10)
                        ):
                            break
                    if not model_ids:
                        continue
                    campaign = store.create_campaign(
                        source_id=source["id"],
                        profile_id=policy.get("profile_id", "diagnostics-v1"),
                        model_ids=model_ids,
                        standing_policy_id=source["id"],
                        budget={
                            "max_attempts": 24,
                            "max_model_requests": int(
                                policy.get("max_model_requests", 80)
                            ),
                            "max_wall_seconds": int(
                                policy.get("max_wall_seconds", 1200)
                            ),
                            "max_tokens": 300000,
                            "cost_limit": None,
                            "case_timeout_seconds": 400,
                        },
                    )
                    manager.start(campaign["id"])
            except Exception:
                pass
            time.sleep(300)

    worker = threading.Thread(
        target=standing_worker,
        name="mtt-standing-policy",
        daemon=True,
    )
    worker.start()

    @server.app.get("/mtt")
    def mtt_page(request: Request):
        return server.templates.TemplateResponse(
            request=request,
            name="mtt.html",
            context={"session_token": server.API_TOKEN},
        )

    @server.app.post("/api/mtt/sources")
    def create_source(payload: SourceRequest):
        if payload.provider not in server.BackendFactory.REGISTRY:
            raise HTTPException(status_code=400, detail="Unsupported MTT source.")
        if payload.provider not in model_sources.LOCAL:
            if payload.endpoint and not payload.endpoint.startswith("http"):
                raise HTTPException(
                    status_code=400,
                    detail="Source endpoint must be an HTTP/HTTPS URL.",
                )
        endpoint = payload.endpoint
        if not endpoint:
            endpoint = {
                "lm_studio": "http://localhost:1234/v1",
                "ollama": "http://localhost:11434",
                "openai": "https://api.openai.com/v1",
                "openrouter": "https://openrouter.ai/api/v1",
                "anthropic": "https://api.anthropic.com",
                "azure_openai": "",
                "groq": "https://api.groq.com/openai/v1",
                "together": "https://api.together.ai/v1",
            }.get(payload.provider, "")
        credential_ref = ""
        if payload.provider in server.BACKEND_KEY_VAR:
            credential_ref = server.BACKEND_KEY_VAR[payload.provider]
        if payload.provider == "openrouter":
            credential_ref = "OPENROUTER_API_KEY"
        source = store.create_source(
            provider=payload.provider,
            name=payload.name,
            endpoint=endpoint,
            account_alias=payload.account_alias,
            credential_ref=credential_ref,
            standing_policy=payload.standing_policy,
        )
        return source

    @server.app.get("/api/mtt/sources")
    def list_sources():
        return {"sources": store.list_sources()}

    @server.app.post("/api/mtt/sources/{source_id}/refresh")
    def refresh_source(source_id: str):
        source = store.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Unknown MTT source.")
        discovery = normalize_discovery(source["provider"], source["endpoint"])
        store.save_catalog(
            source_id,
            discovery["entries"],
            status=discovery["status"],
            error=discovery.get("error", ""),
        )
        store.update_source_status(
            source_id,
            discovery["status"],
            discovery.get("error", ""),
        )
        return store.list_catalog(source_id)

    @server.app.get("/api/mtt/sources/{source_id}/models")
    def list_source_models(source_id: str, include_unlisted: bool = True):
        if not store.get_source(source_id):
            raise HTTPException(status_code=404, detail="Unknown MTT source.")
        return store.list_catalog(source_id, include_unlisted=include_unlisted)

    @server.app.post("/api/mtt/sources/{source_id}/standing-policy")
    def set_standing_policy(source_id: str, payload: StandingPolicyRequest):
        source = store.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Unknown MTT source.")
        store.update_source_status(
            source_id,
            source["status"],
            source["last_error"],
            standing_policy=payload.model_dump(),
        )
        return store.get_source(source_id)

    @server.app.delete("/api/mtt/sources/{source_id}")
    def delete_source(source_id: str):
        source = store.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Unknown MTT source.")
        store.delete_source(source_id)
        return {"status": "removed", "source_id": source_id}

    @server.app.post("/api/mtt/campaigns")
    def create_campaign(payload: CampaignRequest):
        source = store.get_source(payload.source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Unknown MTT source.")
        if source["status"] in {"removed", "failed", "configuration_required"}:
            raise HTTPException(
                status_code=409,
                detail=f"MTT source is unavailable: {source['status']}.",
            )
        catalog = store.list_catalog(
            payload.source_id,
            include_unlisted=False,
        )
        listed_ids = {
            entry["model_id"]
            for entry in catalog["entries"]
            if entry["listed"]
        }
        unknown = [model_id for model_id in payload.model_ids if model_id not in listed_ids]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail="Selected models are not in the current listed catalog: "
                + ", ".join(sorted(unknown)),
            )
        from debugging.dashboard.experiments import JOBS

        with service_lock:
            if any(job.get("status") == "running" for job in JOBS.values()):
                raise HTTPException(
                    status_code=409,
                    detail="Stop or finish the active model experiment before starting MTT.",
                )
        campaign = store.create_campaign(
            source_id=payload.source_id,
            profile_id=payload.profile_id,
            model_ids=payload.model_ids,
            budget={
                "max_attempts": payload.max_attempts,
                "max_model_requests": payload.max_model_requests,
                "max_wall_seconds": payload.max_wall_seconds,
                "max_tokens": payload.max_tokens,
                "cost_limit": payload.cost_limit,
                "case_timeout_seconds": payload.case_timeout_seconds,
            },
            standing_policy_id=payload.standing_policy_id,
        )
        manager.start(campaign["id"])
        return store.get_campaign(campaign["id"])

    @server.app.get("/api/mtt/campaigns")
    def list_campaigns(limit: int = 100):
        return {"campaigns": store.list_campaigns(limit)}

    @server.app.get("/api/mtt/campaigns/{campaign_id}")
    def get_campaign(campaign_id: str):
        campaign = store.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Unknown MTT campaign.")
        return campaign

    @server.app.post("/api/mtt/campaigns/{campaign_id}/cancel")
    def cancel_campaign(campaign_id: str):
        campaign = store.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Unknown MTT campaign.")
        return manager.cancel(campaign_id)

    @server.app.get("/api/mtt/qualifications")
    def list_qualifications(profile_id: str = ""):
        return {"qualifications": store.list_qualifications(profile_id or None)}

    @server.app.post("/api/mtt/recommendations")
    def recommendations(payload: RecommendationRequest):
        return store.recommend(
            profile_id=payload.profile_id,
            application_requirements={
                "free_only": payload.free_only,
                "deadline_seconds": payload.deadline_seconds,
                "provider": payload.provider,
            },
        )
