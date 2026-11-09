"""SSE keep-alive for streamed agent responses (version-03 P10 fix, 2026-11-07).

A turn can go quiet for minutes while a long tool runs (a Goldfish review sends nothing until
its reviewers finish). Proxies drop idle responses: the Cloudflare tunnel closed the stream after
about two minutes of silence, the run was cancelled with it. This ASGI middleware sends an SSE
comment line (`: keep-alive`) when a `text/event-stream` response has sent nothing for
`interval` seconds. SSE clients ignore comment lines (ADK's dev UI, the AG-UI client).
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
ASGIApp = Callable[
    [Scope, Callable[[], Awaitable[Message]], Callable[[Message], Awaitable[None]]], Awaitable[None]
]

KEEPALIVE = b": keep-alive\n\n"
DEFAULT_INTERVAL = 15.0


class SseKeepAliveMiddleware:
    def __init__(self, app: ASGIApp, interval: float = DEFAULT_INTERVAL):
        self.app = app
        self.interval = interval

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        lock = asyncio.Lock()
        state = {"sse": False, "done": False, "last": 0.0}
        loop = asyncio.get_running_loop()
        ticker: asyncio.Task | None = None

        async def tick() -> None:
            while not state["done"]:
                await asyncio.sleep(max(0.05, state["last"] + self.interval - loop.time()))
                async with lock:
                    if state["done"]:
                        return
                    if loop.time() - state["last"] >= self.interval:
                        try:
                            await send(
                                {"type": "http.response.body", "body": KEEPALIVE, "more_body": True}
                            )
                        except Exception:  # client gone: the app sees it on its next send
                            state["done"] = True
                            return
                        state["last"] = loop.time()

        async def wrapped_send(message: Message) -> None:
            nonlocal ticker
            async with lock:
                if message["type"] == "http.response.start":
                    headers = dict(message.get("headers") or [])
                    content_type = headers.get(b"content-type", b"").lower()
                    state["sse"] = content_type.startswith(b"text/event-stream")
                elif message["type"] == "http.response.body" and not message.get("more_body"):
                    state["done"] = True
                await send(message)
                state["last"] = loop.time()
            if state["sse"] and ticker is None and not state["done"]:
                ticker = asyncio.create_task(tick())

        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            state["done"] = True
            if ticker is not None:
                ticker.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await ticker
