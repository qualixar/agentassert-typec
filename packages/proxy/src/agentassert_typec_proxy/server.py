from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agentassert_typec_core.monitor.session import SessionMonitor
from agentassert_typec_proxy import forwarder
from agentassert_typec_proxy.hot_reload import ContractWatcher
from agentassert_typec_proxy.routes import anthropic, openai, gemini, openrouter


def create_app(contract_path: str) -> FastAPI:
    monitor_store: dict = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            monitor = SessionMonitor.from_yaml(contract_path)
        except Exception as e:
            raise RuntimeError(f"Failed to load contract: {e}")

        monitor_store["monitor"] = monitor
        app.state.monitor = monitor

        watcher = ContractWatcher(contract_path)
        watcher.set_monitor(monitor)
        watcher.start()
        app.state.watcher = watcher

        yield

        if "monitor" in monitor_store:
            monitor_store["monitor"].close()
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
        return {
            "status": "ok",
            "contract": monitor._contract.name,
            "theta": monitor._theta.compute(),
        }

    @app.get("/status")
    async def status(request: Request):
        monitor = request.app.state.monitor
        drift_report = monitor._drift.report()
        return {
            "theta": monitor._theta.compute(),
            "drift": {
                "jsd": drift_report.current_jsd,
                "window": drift_report.window_size,
            },
            "violations": len(monitor._violations.all_violations()),
        }

    @app.post("/admin/reload")
    async def admin_reload(request: Request):
        watcher = request.app.state.watcher
        new_monitor = watcher.swap_if_pending()
        if new_monitor:
            request.app.state.monitor = new_monitor
            return JSONResponse({"status": "reloaded", "contract": new_monitor._contract.name})
        return JSONResponse({"status": "no_change"})

    return app
