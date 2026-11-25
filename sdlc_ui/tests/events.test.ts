import assert from "node:assert/strict";
import { test } from "node:test";

import { EventType } from "@ag-ui/client";

import { adkToAgui, chatSummaries, historyMessages, latestUserText } from "../lib/events.ts";

const types = (events: { type: string }[]) => events.map((e) => e.type);

test("text, tool calls and tool results become AG-UI events (snake_case and camelCase)", () => {
  const text = adkToAgui({ id: "e1", author: "user_agent", content: { parts: [{ text: "Hello" }, { text: "hidden", thought: true }] } });
  assert.deepEqual(types(text), [EventType.TEXT_MESSAGE_START, EventType.TEXT_MESSAGE_CONTENT, EventType.TEXT_MESSAGE_END]);
  assert.equal((text[1] as unknown as { delta: string }).delta, "Hello");

  const snake = adkToAgui({ id: "e2", content: { parts: [{ function_call: { id: "c1", name: "knowledge_search", args: { query: "x" } } }] } });
  const camel = adkToAgui({ id: "e2", content: { parts: [{ functionCall: { id: "c1", name: "knowledge_search", args: { query: "x" } } }] } });
  assert.deepEqual(snake, camel);
  assert.deepEqual(types(snake), [EventType.TOOL_CALL_START, EventType.TOOL_CALL_ARGS, EventType.TOOL_CALL_END]);

  const result = adkToAgui({ id: "e3", content: { parts: [{ function_response: { id: "c1", response: { results: [] } } }] } });
  assert.deepEqual(types(result), [EventType.TOOL_CALL_RESULT]);
  assert.equal((result[0] as unknown as { toolCallId: string }).toolCallId, "c1");
});

test("partial, user-authored and empty events are skipped; errors end the run without details", () => {
  assert.deepEqual(adkToAgui({ partial: true, content: { parts: [{ text: "x" }] } }), []);
  assert.deepEqual(adkToAgui({ author: "user", content: { parts: [{ text: "x" }] } }), []);
  assert.deepEqual(adkToAgui(null), []);
  const error = adkToAgui({ error: { code: 400, message: "quoted request" } });
  assert.deepEqual(types(error), [EventType.RUN_ERROR]);
  assert.ok(!JSON.stringify(error).includes("quoted request"));
});

test("a stored session becomes chat history", () => {
  const session = {
    events: [
      { id: "u1", author: "user", content: { parts: [{ text: "What is FR-KNOW-002?" }] } },
      { id: "a1", author: "user_agent", content: { parts: [{ function_call: { id: "c1", name: "knowledge_search", args: { query: "FR-KNOW-002" } } }] } },
      { id: "t1", author: "user_agent", content: { parts: [{ function_response: { id: "c1", name: "knowledge_search", response: { ok: 1 } } }] } },
      { id: "a2", author: "user_agent", content: { parts: [{ text: "Knowledge search, see [FR-KNOW-002](link)." }] } },
      { id: "s1", author: "user_agent", actions: { state_delta: { sdlc_title: "x" } } },
    ],
  };
  const messages = historyMessages(session);
  assert.deepEqual(
    messages.map((m) => m.role),
    ["user", "assistant", "tool", "assistant"],
  );
  assert.equal(messages[0].content, "What is FR-KNOW-002?");
  assert.equal((messages[1].toolCalls as { function: { name: string } }[])[0].function.name, "knowledge_search");
  assert.equal(messages[2].toolCallId, "c1");
  assert.deepEqual(historyMessages({}), []);
});

test("chat summaries, newest first, titled from session state", () => {
  const chats = chatSummaries({
    sessions: [
      { id: "1", state: { sdlc_title: "Older" }, lastUpdateTime: 1_800_000_000 },
      { id: "2", state: {}, last_update_time: 1_800_000_100 },
      { id: "../bad", state: {} },
    ],
  });
  assert.deepEqual(
    chats.map((c) => [c.id, c.title]),
    [
      ["2", "New chat"],
      ["1", "Older"],
    ],
  );
});

test("only the latest user turn is sent", () => {
  const text = latestUserText([
    { role: "user", content: "first" },
    { role: "assistant", content: "answer" },
    { role: "user", content: [{ type: "text", text: "second" }] },
  ]);
  assert.equal(text, "second");
});
