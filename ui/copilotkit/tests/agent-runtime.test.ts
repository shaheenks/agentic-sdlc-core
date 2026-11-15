// The agent-runtime backend (CH-0016): ADK events from Agent Runtime become the AG-UI events the
// chat already renders, the engine is called as the UI service account with the user's token as
// `user_token`, and refusals end the run.

import assert from "node:assert/strict";
import { createServer, type IncomingHttpHeaders } from "node:http";
import type { AddressInfo } from "node:net";
import { after, before, test } from "node:test";

import { type BaseEvent, EventType, type RunAgentInput } from "@ag-ui/client";

import { adkToAgui, AgentRuntimeAgent, EngineClient, engineSettings, latestUserText } from "../lib/agent-runtime.ts";
import { ServiceTokens } from "../lib/gcp.ts";
import { engineHistory } from "../lib/runtime.ts";

const ENGINE = "projects/p1/locations/asia-southeast1/reasoningEngines/123";
const USER_TOKEN = "user.id.token";

// --- mapping (golden) --------------------------------------------------------------------------

test("assistant text becomes one text message", () => {
  const events = adkToAgui({ id: "e1", author: "user_agent", content: { role: "model", parts: [{ text: "Hi " }, { text: "there" }] } });
  assert.deepEqual(events, [
    { type: EventType.TEXT_MESSAGE_START, messageId: "e1", role: "assistant" },
    { type: EventType.TEXT_MESSAGE_CONTENT, messageId: "e1", delta: "Hi there" },
    { type: EventType.TEXT_MESSAGE_END, messageId: "e1" },
  ]);
});

test("a tool call and its result become AG-UI tool events, the result as JSON text", () => {
  const call = adkToAgui({ id: "e2", author: "user_agent", content: { parts: [{ functionCall: { id: "c1", name: "whoami", args: { explain: true } } }] } });
  assert.deepEqual(call, [
    { type: EventType.TOOL_CALL_START, toolCallId: "c1", toolCallName: "whoami", parentMessageId: "e2" },
    { type: EventType.TOOL_CALL_ARGS, toolCallId: "c1", delta: '{"explain":true}' },
    { type: EventType.TOOL_CALL_END, toolCallId: "c1" },
  ]);
  const response = { content: [{ type: "text", text: "{}" }], isError: false };
  const result = adkToAgui({ id: "e3", author: "user_agent", content: { role: "user", parts: [{ functionResponse: { id: "c1", name: "whoami", response } }] } });
  assert.deepEqual(result, [
    { type: EventType.TOOL_CALL_RESULT, messageId: "e3-r0", toolCallId: "c1", content: JSON.stringify(response), role: "tool" },
  ]);
});

test("the session id, partial events, thoughts and user echoes add nothing", () => {
  assert.deepEqual(adkToAgui({ session: "42" }), []);
  assert.deepEqual(adkToAgui({ id: "e", partial: true, content: { parts: [{ text: "x" }] } }), []);
  assert.deepEqual(adkToAgui({ id: "e", author: "user_agent", content: { parts: [{ text: "hmm", thought: true }] } }), []);
  assert.deepEqual(adkToAgui({ id: "e", author: "user", content: { parts: [{ text: "my question" }] } }), []);
  assert.deepEqual(adkToAgui(null), []);
});

test("a refusal or a model error ends the run without detail", () => {
  assert.deepEqual(adkToAgui({ refusal: { code: "unauthenticated", message: "sign-in required" } }), [
    { type: EventType.RUN_ERROR, message: "sign-in required", code: "unauthenticated" },
  ]);
  const model = adkToAgui({ id: "e", errorCode: "SAFETY", errorMessage: "quoted prompt" });
  assert.equal(model[0].type, EventType.RUN_ERROR);
  assert.doesNotMatch(JSON.stringify(model), /quoted prompt/);
});

test("only the latest user message is sent", () => {
  const input = {
    messages: [
      { id: "1", role: "user", content: "old" },
      { id: "2", role: "assistant", content: "answer" },
      { id: "3", role: "user", content: [{ type: "text", text: "new " }, { type: "text", text: "question" }] },
    ],
  } as unknown as RunAgentInput;
  assert.equal(latestUserText(input), "new question");
});

test("the engine resource names its region", () => {
  assert.deepEqual(engineSettings({ SDLC_AGENT_ENGINE: ENGINE }), { engine: ENGINE, region: "asia-southeast1" });
  assert.throws(() => engineSettings({ SDLC_AGENT_ENGINE: "123" }), /SDLC_AGENT_ENGINE/);
});

// --- against a fake engine and metadata server ---------------------------------------------

const calls: { url: string; headers: IncomingHttpHeaders; body: Record<string, unknown> }[] = [];
let base = "";

const server = createServer((req, res) => {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    if (req.url?.startsWith("/meta/token")) {
      assert.equal(req.headers["metadata-flavor"], "Google");
      res.end(JSON.stringify({ access_token: "sa-access", expires_in: 3600 }));
      return;
    }
    const body = JSON.parse(raw || "{}");
    calls.push({ url: req.url ?? "", headers: req.headers, body });
    if (req.url?.endsWith(":streamQuery?alt=sse")) {
      res.writeHead(200, { "content-type": "text/event-stream" });
      const items =
        body.input.user_token === USER_TOKEN
          ? [
              { session: "42" },
              { id: "e1", author: "user_agent", content: { parts: [{ functionCall: { id: "c1", name: "ping", args: {} } }] } },
              { id: "e2", author: "user_agent", content: { parts: [{ functionResponse: { id: "c1", name: "ping", response: { result: "pong" } } }] } },
              { id: "e3", author: "user_agent", content: { parts: [{ text: "pong" }] } },
            ]
          : [{ refusal: { code: "unauthenticated", message: "sign-in required" } }];
      // one item split across writes, SSE framing on some lines
      const text = items.map((i, n) => (n % 2 ? `data: ${JSON.stringify(i)}\n` : `${JSON.stringify(i)}\n`)).join("");
      res.write(text.slice(0, 17));
      res.end(text.slice(17));
      return;
    }
    res.end(JSON.stringify({ output: { threadId: "t1", messages: [{ id: "m1", role: "user", content: "hello" }] } }));
  });
});

before(async () => {
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
after(() => server.close());

function client(): EngineClient {
  return new EngineClient({ engine: ENGINE, region: "r" }, new ServiceTokens(fetch, `${base}/meta`), fetch, `${base}/v1`);
}

async function runOnce(agent: AgentRuntimeAgent): Promise<BaseEvent[]> {
  const input = { threadId: "t1", runId: "r1", messages: [{ id: "u", role: "user", content: "ping please" }] } as unknown as RunAgentInput;
  const events: BaseEvent[] = [];
  await new Promise<void>((resolve, reject) => agent.run(input).subscribe({ next: (e) => events.push(e), complete: resolve, error: reject }));
  return events;
}

test("a run calls stream_query as the service account with the user's token and thread", async () => {
  calls.length = 0;
  const agent = new AgentRuntimeAgent(client()).clone();
  agent.headers = { "X-Forwarded-Access-Token": USER_TOKEN };
  const events = await runOnce(agent);
  assert.equal(calls[0].url, `/v1/${ENGINE}:streamQuery?alt=sse`);
  assert.equal(calls[0].headers.authorization, "Bearer sa-access");
  assert.deepEqual(calls[0].body, {
    class_method: "stream_query",
    input: { message: "ping please", user_token: USER_TOKEN, thread_id: "t1" },
  });
  assert.deepEqual(
    events.map((e) => e.type),
    [
      EventType.RUN_STARTED,
      EventType.TOOL_CALL_START,
      EventType.TOOL_CALL_ARGS,
      EventType.TOOL_CALL_END,
      EventType.TOOL_CALL_RESULT,
      EventType.TEXT_MESSAGE_START,
      EventType.TEXT_MESSAGE_CONTENT,
      EventType.TEXT_MESSAGE_END,
      EventType.RUN_FINISHED,
    ],
  );
});

test("a refused or token-less run ends with RUN_ERROR and never calls the engine without a token", async () => {
  calls.length = 0;
  const refused = new AgentRuntimeAgent(client());
  refused.headers = { "x-forwarded-access-token": "someone.elses.token" };
  const events = await runOnce(refused);
  assert.deepEqual(events.at(-1), { type: EventType.RUN_ERROR, message: "sign-in required", code: "unauthenticated" });
  calls.length = 0;
  const none = await runOnce(new AgentRuntimeAgent(client()));
  assert.equal(none.at(-1)?.type, EventType.RUN_ERROR);
  assert.equal(calls.length, 0);
});

test("history comes from get_thread as the same user", async () => {
  calls.length = 0;
  const body = await engineHistory(client())("t1", USER_TOKEN, new AbortController().signal);
  assert.deepEqual(calls[0].body, { class_method: "get_thread", input: { user_token: USER_TOKEN, thread_id: "t1" } });
  assert.deepEqual(body, { threadExists: true, messages: [{ id: "m1", role: "user", content: "hello" }] });
  const refused = await engineHistory({ query: async () => ({ refusal: { code: "not_found", message: "x" } }) })("t1", "t", new AbortController().signal);
  assert.deepEqual(refused, { threadExists: false, messages: [] });
});
