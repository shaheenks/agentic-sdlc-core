"""SSE keep-alive (sdlc_web.keepalive): quiet event streams get comment lines, nothing else does."""

import asyncio

from sdlc_web.keepalive import KEEPALIVE, SseKeepAliveMiddleware


def sse_app(content_type: bytes, gap: float):
    async def app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", content_type)],
            }
        )
        await send({"type": "http.response.body", "body": b"data: 1\n\n", "more_body": True})
        await asyncio.sleep(gap)  # a long tool: nothing to send
        await send({"type": "http.response.body", "body": b"data: 2\n\n", "more_body": False})

    return app


async def run(app) -> list[bytes]:
    sent: list[bytes] = []

    async def send(message):
        if message["type"] == "http.response.body":
            sent.append(message.get("body", b""))

    async def receive():
        return {"type": "http.disconnect"}

    await app({"type": "http", "path": "/run_sse"}, receive, send)
    return sent


async def test_quiet_stream_gets_keepalives_and_data_is_unchanged():
    sent = await run(
        SseKeepAliveMiddleware(sse_app(b"text/event-stream; charset=utf-8", 0.35), 0.1)
    )
    assert sent[0] == b"data: 1\n\n" and sent[-1] == b"data: 2\n\n"
    pings = [b for b in sent if b == KEEPALIVE]
    assert 2 <= len(pings) <= 4
    assert b"".join(b for b in sent if b != KEEPALIVE) == b"data: 1\n\ndata: 2\n\n"


async def test_no_keepalive_after_the_end_or_for_other_responses():
    sent = await run(SseKeepAliveMiddleware(sse_app(b"application/json", 0.3), 0.05))
    assert KEEPALIVE not in sent
    middleware = SseKeepAliveMiddleware(sse_app(b"text/event-stream", 0.0), 0.05)
    sent = await run(middleware)
    await asyncio.sleep(0.2)  # the ticker stopped with the response
    assert sent == [b"data: 1\n\n", b"data: 2\n\n"]


async def test_a_client_gone_stops_the_ticker():
    async def app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        await asyncio.sleep(0.3)

    calls = 0

    async def send(message):
        nonlocal calls
        calls += 1
        if message["type"] == "http.response.body":
            raise OSError("client disconnected")

    async def receive():
        return {"type": "http.disconnect"}

    await SseKeepAliveMiddleware(app, 0.05)({"type": "http"}, receive, send)
    assert calls == 2  # the start, then one failed keep-alive; no more tries
