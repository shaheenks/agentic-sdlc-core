import assert from "node:assert/strict";
import { test } from "node:test";

import {
  deleteThreadRequest,
  formatUpdated,
  withoutThread,
  historyMessages,
  latestTurn,
  parseThreads,
  threadFromSearch,
} from "../lib/threads.ts";

test("parseThreads keeps valid entries only", () => {
  const body = {
    threads: [
      { threadId: "3f1c2a7e-0b1d-4a55-9a51-0d5d7c1e9b01", title: "how do refunds work?", updatedAt: "2026-11-04T09:00:00+00:00" },
      { threadId: "../etc/passwd", title: "bad id" },
      { threadId: "no-title", title: "" },
      null,
      "x",
    ],
  };
  assert.deepEqual(parseThreads(body), [
    { id: "3f1c2a7e-0b1d-4a55-9a51-0d5d7c1e9b01", title: "how do refunds work?", updatedAt: "2026-11-04T09:00:00+00:00" },
  ]);
  assert.deepEqual(parseThreads({ detail: "history unavailable" }), []);
  assert.deepEqual(parseThreads(null), []);
});

test("delete requests carry the header and only valid ids", () => {
  const request = deleteThreadRequest("abc-123");
  assert.equal(request?.url, "/threads/abc-123");
  assert.equal(request?.init.method, "DELETE");
  assert.deepEqual(request?.init.headers, { "X-SDLC-Request": "1" });
  assert.equal(deleteThreadRequest("../threads"), null);
  assert.equal(deleteThreadRequest(""), null);
  const list = [
    { id: "a", title: "A", updatedAt: "" },
    { id: "b", title: "B", updatedAt: "" },
  ];
  assert.deepEqual(withoutThread(list, "a").map((t) => t.id), ["b"]);
  assert.equal(withoutThread(list, "zzz").length, 2);
});

test("threadFromSearch accepts only thread ids", () => {
  assert.equal(threadFromSearch("?thread=abc-123"), "abc-123");
  assert.equal(threadFromSearch("?thread=1234567890"), "1234567890");
  assert.equal(threadFromSearch("?thread=a%2Fb"), null);
  assert.equal(threadFromSearch("?thread=<script>"), null);
  assert.equal(threadFromSearch(""), null);
});

test("latestTurn sends from the last user message on", () => {
  const messages = [
    { id: "1", role: "user" },
    { id: "2", role: "assistant" },
    { id: "3", role: "user" },
  ];
  assert.deepEqual(latestTurn(messages).map((m) => m.id), ["3"]);
  assert.deepEqual(latestTurn([{ id: "a", role: "assistant" }]).map((m) => m.id), ["a"]);
  assert.deepEqual(latestTurn([]), []);
});

test("historyMessages keeps conversation messages and drops nulls", () => {
  const body = {
    threadExists: true,
    messages: [
      { id: "u1", role: "user", content: "hi", name: null },
      { id: "a1", role: "assistant", content: null, toolCalls: [{ id: "t1", type: "function", function: { name: "search_knowledge", arguments: "{}" } }] },
      { id: "t1r", role: "tool", content: "{}", toolCallId: "t1" },
      { id: "s1", role: "system", content: "internal" },
      { role: "user", content: "no id" },
    ],
  };
  assert.deepEqual(historyMessages(body), [
    { id: "u1", role: "user", content: "hi" },
    { id: "a1", role: "assistant", toolCalls: [{ id: "t1", type: "function", function: { name: "search_knowledge", arguments: "{}" } }] },
    { id: "t1r", role: "tool", content: "{}", toolCallId: "t1" },
  ]);
  assert.deepEqual(historyMessages({ threadExists: false, messages: [{ id: "x", role: "user" }] }), []);
  assert.deepEqual(historyMessages({ error: "x" }), []);
});

test("formatUpdated shows time today, date otherwise", () => {
  const now = new Date("2026-11-04T12:00:00");
  assert.match(formatUpdated("2026-11-04T09:05:00", now), /09|9/);
  assert.match(formatUpdated("2026-10-03T09:05:00", now), /3/);
  assert.match(formatUpdated("2025-10-03T09:05:00", now), /2025/);
  assert.equal(formatUpdated("not a date", now), "");
});
