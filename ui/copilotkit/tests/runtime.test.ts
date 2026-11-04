// The real CopilotKit runtime handler against a fake /agui server (no network beyond localhost):
// only the proxy's token header is forwarded, nothing is stored or replayed between users.

import assert from "node:assert/strict";
import { createServer, type IncomingHttpHeaders } from "node:http";
import type { AddressInfo } from "node:net";
import { after, before, test } from "node:test";

const TOKEN = "header.payload.signature";
const seen: IncomingHttpHeaders[] = [];

const agui = createServer((req, res) => {
  seen.push(req.headers);
  let body = "";
  req.on("data", (chunk) => (body += chunk));
  req.on("end", () => {
    const input = JSON.parse(body || "{}");
    if (req.url === "/agents/state") {
      // the fake agent's history: only TOKEN's user has thread "old-thread"
      const mine = req.headers["x-forwarded-access-token"] === TOKEN && input.threadId === "old-thread";
      res.writeHead(200, { "content-type": "application/json" });
      res.end(
        JSON.stringify({
          threadId: input.threadId,
          threadExists: mine,
          state: {},
          messages: mine
            ? [
                { id: "u1", role: "user", content: "earlier question", name: null },
                { id: "a1", role: "assistant", content: "earlier answer" },
              ]
            : [],
        }),
      );
      return;
    }
    const ids = { threadId: input.threadId, runId: input.runId };
    const events = [
      { type: "RUN_STARTED", ...ids },
      { type: "TEXT_MESSAGE_START", messageId: "a1", role: "assistant" },
      { type: "TEXT_MESSAGE_CONTENT", messageId: "a1", delta: `secret answer for ${input.threadId}` },
      { type: "TEXT_MESSAGE_END", messageId: "a1" },
      { type: "RUN_FINISHED", ...ids },
    ];
    res.writeHead(200, { "content-type": "text/event-stream" });
    for (const e of events) res.write(`data: ${JSON.stringify(e)}\n\n`);
    res.end();
  });
});

let handler: (request: Request) => Promise<Response>;
const base = "http://app.internal/chat/api/copilotkit";

before(async () => {
  await new Promise<void>((resolve) => agui.listen(0, "127.0.0.1", resolve));
  const { port } = agui.address() as AddressInfo;
  process.env.SDLC_AGUI_URL = `http://127.0.0.1:${port}/agui`;
  process.env.COPILOTKIT_TELEMETRY_DISABLED = "true";
  ({ copilotHandler: handler } = await import("../lib/runtime.ts").then((m) => ({
    copilotHandler: m.copilotHandler(),
  })));
});

after(() => agui.close());

function runInput(threadId: string) {
  return {
    threadId,
    runId: `run-${threadId}`,
    messages: [{ id: "u1", role: "user", content: "hello" }],
    tools: [],
    context: [],
    state: {},
    forwardedProps: {},
  };
}

async function run(threadId: string, headers: Record<string, string>) {
  const response = await handler(
    new Request(`${base}/agent/default/run`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "text/event-stream", ...headers },
      body: JSON.stringify(runInput(threadId)),
    }),
  );
  return { status: response.status, text: await response.text() };
}

test("runs reach /agui with only the proxy token header", async () => {
  const { status, text } = await run("thread-a", {
    "x-forwarded-access-token": TOKEN,
    cookie: "_oauth2_proxy=session-cookie",
    authorization: "Bearer from-browser",
    "x-forwarded-for": "10.0.0.1",
    "x-custom-header": "nope",
  });
  assert.equal(status, 200, text);
  assert.match(text, /secret answer for thread-a/);
  const headers = seen.at(-1)!;
  assert.equal(headers["x-forwarded-access-token"], TOKEN);
  for (const name of ["cookie", "authorization", "x-forwarded-for", "x-custom-header"]) {
    assert.equal(headers[name], undefined, `${name} must not be forwarded`);
  }
});

test("another user cannot replay a thread from this process", async () => {
  await run("thread-b", { "x-forwarded-access-token": TOKEN });
  const response = await handler(
    new Request(`${base}/agent/default/connect`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-forwarded-access-token": "other-user" },
      body: JSON.stringify(runInput("thread-b")),
    }),
  );
  const text = await response.text();
  assert.doesNotMatch(text, /secret answer/);
});

async function connect(threadId: string, headers: Record<string, string>) {
  const response = await handler(
    new Request(`${base}/agent/default/connect`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "text/event-stream", ...headers },
      body: JSON.stringify(runInput(threadId)),
    }),
  );
  return { status: response.status, text: await response.text() };
}

test("opening a thread replays the user's own history from the agent", async () => {
  const { status, text } = await connect("old-thread", {
    "x-forwarded-access-token": TOKEN,
    cookie: "_oauth2_proxy=session-cookie",
  });
  assert.equal(status, 200, text);
  assert.match(text, /MESSAGES_SNAPSHOT/);
  assert.match(text, /earlier question/);
  assert.match(text, /earlier answer/);
  const headers = seen.at(-1)!;
  assert.equal(headers["x-forwarded-access-token"], TOKEN); // asked as the same user
  assert.equal(headers.cookie, undefined);
});

test("another user's token gets no history for the same thread", async () => {
  const other = await connect("old-thread", { "x-forwarded-access-token": "other-user" });
  assert.doesNotMatch(other.text, /earlier question|MESSAGES_SNAPSHOT/);
  const anonymous = await connect("old-thread", {});
  assert.doesNotMatch(anonymous.text, /earlier question|MESSAGES_SNAPSHOT/);
});

test("thread listing and history endpoints are not available", async () => {
  for (const path of ["/threads", "/threads/thread-a/messages", "/threads/thread-a/events"]) {
    const response = await handler(new Request(`${base}${path}`, { method: "GET" }));
    const text = await response.text();
    assert.notEqual(response.status, 200, `${path}: ${text}`);
    assert.doesNotMatch(text, /secret answer/);
  }
});
