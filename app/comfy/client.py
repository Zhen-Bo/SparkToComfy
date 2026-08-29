"""The ComfyUI boundary: HTTP through httpx, the event stream through websockets.

Exceptions go out unchanged. httpx.HTTPStatusError carries the status code and
httpx.RequestError separates "cannot connect" from "timed out", so the router layer
decides which HTTP status each one becomes.
"""

import asyncio
import json
import struct
from urllib.parse import quote, urlparse

import httpx
import structlog
import websockets

from app.comfy.config import SETTINGS

logger = structlog.stdlib.get_logger(__name__)

COMFY_URL = SETTINGS.url.rstrip("/")
CLIENT_ID = "comfypanel-backend"
TIMEOUT = 30.0
RETRY_FIRST = 1.0  # first reconnect backoff, in seconds
RETRY_CAP = 30.0  # reconnect backoff ceiling, in seconds
_LORA_PAGE = 100
_PREVIEW_EVENT = 4  # ComfyUI binary frame event type: preview image
_TEXT_TYPES = frozenset(
    {
        "status",
        "execution_start",
        "progress",
        "execution_success",
        "execution_error",
        "execution_interrupted",
    }
)


class ComfyError(Exception):
    """ComfyUI rejected the prompt with a 400. payload is the body it sent back."""

    def __init__(self, payload: dict):
        self.payload = payload


def _ws_url(http_url: str) -> str:
    parsed = urlparse(http_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/ws?clientId={CLIENT_ID}"


def collect_images(hist: dict) -> list[dict]:
    images = []
    for out in (hist.get("outputs") or {}).values():
        for img in out.get("images") or []:
            if img.get("type") == "output":
                images.append(
                    {
                        "filename": img["filename"],
                        "subfolder": img["subfolder"],
                        "type": img["type"],
                    }
                )
    return images


class ComfyClient:
    def __init__(
        self,
        base_url: str = COMFY_URL,
        timeout: float = TIMEOUT,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self.http.aclose()

    # --- HTTP ---

    async def _get_json(self, path: str, params: dict | None = None) -> dict:
        resp = await self.http.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def submit_prompt(self, prompt: dict, prompt_id: str) -> dict:
        resp = await self.http.post(
            "/api/prompt",
            json={"prompt": prompt, "client_id": CLIENT_ID, "prompt_id": prompt_id},
        )
        if resp.status_code == 400:
            raise ComfyError(resp.json())
        resp.raise_for_status()
        return resp.json()

    async def cancel_job(self, prompt_id: str) -> dict:
        resp = await self.http.post(
            f"/api/jobs/{quote(prompt_id, safe='')}/cancel", json={}
        )
        resp.raise_for_status()
        return resp.json()

    async def get_queue(self) -> dict:
        return await self._get_json("/api/queue")

    async def get_history(self, prompt_id: str) -> dict | None:
        resp = await self._get_json(f"/api/history/{prompt_id}")
        return resp.get(prompt_id)

    async def list_loras(self) -> list[dict]:
        first = await self._get_json("/api/lm/loras/list", {"page_size": _LORA_PAGE})
        items = list(first.get("items") or [])
        for page in range(2, (first.get("total_pages") or 1) + 1):
            more = await self._get_json(
                "/api/lm/loras/list", {"page_size": _LORA_PAGE, "page": page}
            )
            items.extend(more.get("items") or [])
        return items

    async def fetch_preview(self, preview_url: str) -> tuple[bytes, str]:
        resp = await self.http.get(preview_url)
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "application/octet-stream")
        return resp.content, ctype

    async def stream_view(self, ref: dict) -> httpx.Response:
        """Open a streaming response for an output image. The caller must aclose() it."""
        request = self.http.build_request(
            "GET",
            "/api/view",
            params={
                "filename": ref["filename"],
                "subfolder": ref["subfolder"],
                "type": ref["type"],
            },
        )
        resp = await self.http.send(request, stream=True)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            await resp.aclose()
            raise
        return resp

    # --- event stream ---

    async def _on_message(self, on_event, raw) -> None:
        if isinstance(raw, bytes):
            if len(raw) < 8:
                return
            (event_type,) = struct.unpack_from(">I", raw, 0)
            if event_type != _PREVIEW_EVENT:
                return
            (meta_len,) = struct.unpack_from(">I", raw, 4)
            start = 8
            end = start + meta_len
            if end > len(raw):
                return
            metadata = json.loads(raw[start:end])
            await on_event("preview", {**metadata, "bytes": raw[end:]})
            return
        msg = json.loads(raw)
        kind = msg.get("type")
        if kind in _TEXT_TYPES:
            await on_event(kind, msg.get("data") or {})

    async def _run_connection(self, on_event) -> None:
        async with websockets.connect(_ws_url(self.base_url), max_size=None) as socket:
            await socket.send(
                json.dumps(
                    {
                        "type": "feature_flags",
                        "data": {"supports_preview_metadata": True},
                    }
                )
            )
            await on_event("connected", {})
            async for raw in socket:
                await self._on_message(on_event, raw)

    async def listen(self, on_event) -> None:
        """Read while connected, back off and reconnect when dropped.

        Only cancellation leaves this loop.
        """
        delay = RETRY_FIRST
        logged = False
        while True:
            try:
                await self._run_connection(on_event)
                delay = RETRY_FIRST
                logged = False
            except asyncio.CancelledError:
                raise
            except (OSError, websockets.WebSocketException, TimeoutError) as err:
                if not logged:
                    logger.warning(
                        "ComfyUI connection failed, retrying with backoff",
                        url=self.base_url,
                        cap_seconds=RETRY_CAP,
                        error=repr(err),
                    )
                    logged = True
            await on_event("disconnected", {})
            await asyncio.sleep(delay)
            delay = min(delay * 2, RETRY_CAP)
