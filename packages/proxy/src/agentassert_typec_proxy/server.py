from __future__ import annotations

import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agentassert_typec_core.monitor.session import SessionMonitor
from agentassert_typec_proxy import forwarder
from agentassert_typec_proxy.hot_reload import ContractWatcher
from agentassert_typec_proxy.routes import anthropic, openai, gemini, openrouter


def _extract_upstream(monitor: SessionMonitor) -> dict[str, str] | None:
    upstream = getattr(monitor._contract, "upstream", None)
    if upstream is None:
        return None
    result = {}
    for provider in ("anthropic", "openai", "gemini", "openrouter"):
        url = getattr(upstream, provider, None)
        if url:
            result[provider] = url
    return result or None


def _resolve_db_path(contract_path: str, session_id: str | None = None) -> str:
    """Resolve the SQLite DB path for a given contract + optional session_id."""
    slug = re.sub(r"[^a-z0-9]+", "-", Path(contract_path).stem.lower()).strip("-")
    if session_id:
        slug = f"{slug}_{session_id}"
    db_dir = Path.home() / ".agentassert" / "sessions"
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / f"{slug}.db")


def create_app(
    contract_path: str,
    session_id: str | None = None,
    persist: bool = True,
) -> FastAPI:
    monitor_store: dict = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            monitor = SessionMonitor.from_yaml(contract_path)
        except Exception as e:
            raise RuntimeError(f"Failed to load contract: {e}")

        monitor_store["monitor"] = monitor
        app.state.monitor = monitor
        app.state.upstream_overrides = _extract_upstream(monitor)
        app.state.db_path = None

        # Phase 2: attach persistence store
        if persist:
            from agentassert_typec_core.persistence.sqlite_store import SessionStore
            db_path = _resolve_db_path(contract_path, session_id)
            store = SessionStore(db_path)
            store.open()
            monitor.attach_store(store)
            app.state.db_path = db_path
            app.state.store = store

        watcher = ContractWatcher(contract_path)
        watcher.set_monitor(monitor)
        watcher.start()
        app.state.watcher = watcher

        yield

        if "monitor" in monitor_store:
            monitor_store["monitor"].close()  # flushes + closes store
        app.state.watcher.stop()
        if forwarder._client is not None:
            await forwarder._client.aclose()

    app = FastAPI(lifespan=lifespan)
    app.state.contract_name = contract_path

    app.include_router(anthropic.router, prefix="/anthropic")
    app.include_router(openai.router, prefix="/openai")
    app.include_router(gemini.router, prefix="/gemini")
    app.include_router(openrouter.router, prefix="/openrouter")

    @app.get("/health")
    async def health(request: Request):
        monitor = request.app.state.monitor
        db_path = getattr(request.app.state, "db_path", None)
        store = getattr(request.app.state, "store", None)
        persistence = {
            "enabled": db_path is not None,
            "db_path": db_path,
            "dirty": store.is_dirty() if store is not None else False,
        }
        return {
            "status": "ok",
            "contract": monitor._contract.name,
            "theta": monitor._theta.compute(),
            "upstream": request.app.state.upstream_overrides or "defaults",
            "persistence": persistence,
        }

    @app.get("/status")
    async def status(request: Request):
        monitor = request.app.state.monitor
        drift_report = monitor._drift.report()

        # Phase 3: cost section
        ceiling_config = monitor._compiled.cost_ceiling_config
        with monitor._cost_lock:
            accumulated = monitor._accumulated_cost_usd
        ceiling_usd = ceiling_config.max_usd_per_session if ceiling_config else None
        remaining = (ceiling_usd - accumulated) if ceiling_usd is not None else None
        pct_used = (accumulated / ceiling_usd * 100.0) if ceiling_usd else None

        return {
            "theta": monitor._theta.compute(),
            "drift": {
                "jsd": drift_report.current_jsd,
                "window": drift_report.window_size,
            },
            "violations": len(monitor._violations.all_violations()),
            "cost": {
                "accumulated_usd": accumulated,
                "ceiling_usd": ceiling_usd,
                "remaining_usd": remaining,
                "pct_used": round(pct_used, 1) if pct_used is not None else None,
            },
        }

    @app.post("/admin/reload")
    async def admin_reload(request: Request):
        watcher = request.app.state.watcher
        new_monitor = watcher.swap_if_pending()
        if new_monitor:
            request.app.state.monitor = new_monitor
            request.app.state.upstream_overrides = _extract_upstream(new_monitor)
            return JSONResponse({"status": "reloaded", "contract": new_monitor._contract.name})
        return JSONResponse({"status": "no_change"})

    return app
