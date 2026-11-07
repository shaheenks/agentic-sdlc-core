import assert from "node:assert/strict";
import { test } from "node:test";

import { KEEPALIVE, withKeepAlive } from "../lib/keepalive.ts";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function slowStream(chunks: string[], gapMs: number): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    async start(controller) {
      for (const c of chunks) {
        await sleep(gapMs);
        controller.enqueue(enc.encode(c));
      }
      controller.close();
    },
  });
}

test("a quiet event stream gets keep-alive comments, data unchanged", async () => {
  const inner = new Response(slowStream(["data: 1\n\n", "data: 2\n\n"], 250), {
    headers: { "content-type": "text/event-stream" },
  });
  const text = await withKeepAlive(inner, 60).text();
  assert.ok(text.includes(KEEPALIVE), text);
  assert.equal(text.replaceAll(KEEPALIVE, ""), "data: 1\n\ndata: 2\n\n");
});

test("other responses are passed through untouched", async () => {
  const json = new Response("{}", { headers: { "content-type": "application/json" } });
  assert.equal(withKeepAlive(json, 10), json);
});
