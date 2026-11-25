import assert from "node:assert/strict";
import { test } from "node:test";

import { EventType } from "@ag-ui/client";

import { adkToAgui, chatSummaries, historyMessages, latestUserText, turnInput } from "../lib/events.ts";

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

// Workflows (phase 4a milestone 4) ---------------------------------------------------------------------------

const question = { id: "q1", name: "adk_request_input", args: { message: "Apply?", payload: { kind: "review_findings" } } };

test("a workflow's agents stay out of the chat; only its questions reach it", () => {
  assert.deepEqual(adkToAgui({ id: "r", author: "review_design", content: { parts: [{ text: '{"findings": []}' }] } }), []);
  assert.deepEqual(adkToAgui({ id: "d", author: "features_drafter", content: { parts: [{ text: "# Draft" }] } }), []);
  const asked = adkToAgui({ id: "w", author: "features_and_stories", content: { parts: [{ function_call: question }] } });
  assert.deepEqual(types(asked), [EventType.TOOL_CALL_START, EventType.TOOL_CALL_ARGS, EventType.TOOL_CALL_END]);
  assert.equal((asked[0] as unknown as { toolCallName: string }).toolCallName, "adk_request_input");
});

test("an answer to a question this chat asked resumes the workflow; anything else is plain text", () => {
  const asked = { role: "assistant", toolCalls: [{ id: "q1", type: "function", function: { name: "adk_request_input", arguments: "{}" } }] };
  assert.deepEqual(turnInput([{ role: "user", content: "go" }, asked, { role: "tool", toolCallId: "q1", content: '"F1, F2"' }]), {
    role: "user",
    parts: [{ function_response: { id: "q1", name: "adk_request_input", response: { result: "F1, F2" } } }],
  });
  // a tool message for a call this chat never made, or for another tool, is not an answer
  assert.equal(turnInput([{ role: "user", content: "go" }, { role: "tool", toolCallId: "q9", content: "x" }]), "go");
  const other = { role: "assistant", toolCalls: [{ id: "c1", type: "function", function: { name: "artifact_save", arguments: "{}" } }] };
  assert.equal(turnInput([{ role: "user", content: "go" }, other, { role: "tool", toolCallId: "c1", content: "x" }]), "go");
  assert.equal(turnInput([{ role: "user", content: "hello" }]), "hello");
});

test("a reopened chat shows the workflow's questions and the user's answers, not its agents", () => {
  const messages = historyMessages({
    events: [
      { id: "u1", author: "user", content: { parts: [{ text: "draft it" }] } },
      { id: "r1", author: "review_style", content: { parts: [{ text: '{"findings": []}' }] } },
      { id: "q", author: "features_and_stories", content: { parts: [{ function_call: question }] } },
      { id: "a", author: "user", content: { parts: [{ function_response: { id: "q1", name: "adk_request_input", response: { result: "stop" } } }] } },
    ],
  });
  assert.deepEqual(
    messages.map((m) => m.role),
    ["user", "assistant", "tool"],
  );
  assert.equal(messages[2].toolCallId, "q1");
});

test("a team chat is listed with its team", () => {
  const [chat] = chatSummaries({ sessions: [{ id: "s1", state: { sdlc_title: "Refunds", sdlc_team: "payments" }, lastUpdateTime: 1 }] });
  assert.equal(chat.team, "payments");
});
