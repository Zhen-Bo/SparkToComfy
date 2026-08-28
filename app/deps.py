"""The only entry point through which routes get the Runtime."""

from typing import Annotated

from fastapi import Depends, Request, WebSocket

from app.runtime import Runtime


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


def ws_runtime(websocket: WebSocket) -> Runtime:
    return websocket.app.state.runtime


RuntimeDep = Annotated[Runtime, Depends(get_runtime)]
WsRuntimeDep = Annotated[Runtime, Depends(ws_runtime)]
