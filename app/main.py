"""The outer app serves the SPA; the API and the WebSocket live in a sub-app under /v1.

Starlette matches a Mount by prefix, so every path below /v1 enters the sub-app and an unknown route gets the sub-app's own JSON 404.
The SPA catch-all can never shadow it, so no reserved-prefix list is needed.
Docs follow the sub-app: /v1/docs, /v1/openapi.json, /v1/redoc.
"""

import asyncio
import json
from contextlib import asynccontextmanager, suppress

import structlog
import yaml
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config, errors, log, runtime
from app.config import WorkflowCatalog
from app.forms.router import router as forms_router
from app.history.router import router as history_router
from app.images.router import router as images_router
from app.jobs.router import router as jobs_router
from app.lora.router import router as lora_router
from app.settings import ROOT
from app.ws.router import router as ws_router

logger = structlog.stdlib.get_logger(__name__)

RELOAD_SECONDS = 30
UI_DIR = ROOT / "frontend" / "dist"


async def _reload_loop(catalog: WorkflowCatalog) -> None:
    while True:
        await asyncio.sleep(RELOAD_SECONDS)
        try:
            await asyncio.to_thread(catalog.reload)
        except (OSError, yaml.YAMLError, json.JSONDecodeError, KeyError, RuntimeError):
            logger.exception("Workflow reload failed, keeping the previous declaration")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    rt = await runtime.build()
    # Routes live on the sub-app and Starlette sets scope["app"] to it, so state goes here.
    api.state.runtime = rt
    tasks = [
        asyncio.create_task(rt.comfy.listen(rt.events.handle)),
        asyncio.create_task(_reload_loop(rt.catalog)),
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
app.mount("/v1", api)

if UI_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=UI_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        candidate = (UI_DIR / path).resolve()
        if path and candidate.is_file() and UI_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(UI_DIR / "index.html")
