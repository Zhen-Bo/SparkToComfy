"""The outer app serves the SPA; the API and the WebSocket live in a sub-app under /v1.

Starlette matches a Mount by prefix, so every path below /v1 enters the sub-app and an unknown route gets the sub-app's own JSON 404.
The SPA catch-all can never shadow it, so no reserved-prefix list is needed.
Docs follow the sub-app: /v1/docs, /v1/openapi.json, /v1/redoc.
"""

import asyncio
from contextlib import asynccontextmanager, suppress

import structlog
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.body_limit import RequestBodyLimitMiddleware

from app import config, errors, log, runtime
from app.config import WorkflowCatalog
from app.forms.router import router as forms_router
from app.history.router import router as history_router
from app.images.router import router as images_router
from app.jobs.config import RECONCILE
from app.jobs.router import router as jobs_router
from app.lora.router import router as lora_router
from app.settings import ROOT
from app.ws.router import router as ws_router

logger = structlog.stdlib.get_logger(__name__)

RELOAD_SECONDS = 30
# Request bodies are JSON parameters, a few KB at most.
MAX_BODY_BYTES = 64 * 1024
UI_DIR = ROOT / "frontend" / "dist"


async def _reload_loop(catalog: WorkflowCatalog) -> None:
    while True:
        await asyncio.sleep(RELOAD_SECONDS)
        try:
            await asyncio.to_thread(catalog.reload)
        except Exception:
            logger.exception("Workflow reload failed, keeping the previous declaration")


async def _reconcile_loop(rt: runtime.Runtime) -> None:
    """Compare the ComfyUI queue against the jobs in flight, on a fixed beat.

    Nothing here is needed while every ComfyUI event arrives; it exists for the case where one
    does not. A pass that raises must not end the beat, or the safety net is gone for good.
    """
    while True:
        await asyncio.sleep(RECONCILE.interval_seconds)
        try:
            await rt.events.refresh_positions()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reconcile pass failed, retrying on the next beat")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    rt = await runtime.build()
    # Routes live on the sub-app and Starlette sets scope["app"] to it, so state goes here.
    api.state.runtime = rt
    tasks = [
        asyncio.create_task(rt.comfy.listen(rt.events.handle)),
        asyncio.create_task(_reload_loop(rt.catalog)),
        asyncio.create_task(_reconcile_loop(rt)),
    ]
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task
    await rt.aclose()


log.setup(config.SETTINGS.log_format, config.SETTINGS.log_level)
api = FastAPI(
    title="comfyPanel backend",
    openapi_url="/openapi.json" if config.SETTINGS.docs else None,
)
errors.install(api)
api.include_router(forms_router)
api.include_router(lora_router)
api.include_router(jobs_router)
api.include_router(history_router)
api.include_router(images_router)
api.include_router(ws_router)

app = FastAPI(lifespan=lifespan, openapi_url=None)
app.add_middleware(RequestBodyLimitMiddleware, max_body_size=MAX_BODY_BYTES)
app.mount("/v1", api)

if UI_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=UI_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        candidate = (UI_DIR / path).resolve()
        if path and candidate.is_file() and UI_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(UI_DIR / "index.html")
