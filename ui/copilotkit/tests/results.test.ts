import assert from "node:assert/strict";
import { test } from "node:test";

import { citations, graphEntities, identity, location, safeUrl, toolPayload } from "../lib/results.ts";

const search = {
  query: "restart ledger",
  results: [
    {
      source: "payments-confluence",
      path: "PAY/123",
      title: "Ledger runbook",
      url: "https://acme.atlassian.net/wiki/spaces/PAY/pages/123",
      lines: [1, 20],
      heading: "Restart",
      score: 0.91,
      snippet: "kubectl rollout restart",
    },
    { source: "eng-standards", path: "policy.pdf", pages: [3, 3], snippet: "p3", url: "javascript:alert(1)" },
  ],
};

test("tool payloads unwrap every envelope", () => {
  const text = JSON.stringify(search);
  for (const raw of [
    search,
    text,
    { structuredContent: search },
    JSON.stringify({ content: [{ type: "text", text }] }),
    { result: text },
  ]) {
    assert.deepEqual(toolPayload(raw), search);
  }
  assert.equal(toolPayload("not json"), null);
  assert.equal(toolPayload(null), null);
});

test("citations keep only http(s) links", () => {
  const [conf, pdf] = citations(JSON.stringify({ structuredContent: search }));
  assert.equal(conf.title, "Ledger runbook");
  assert.equal(conf.url, "https://acme.atlassian.net/wiki/spaces/PAY/pages/123");
  assert.equal(location(conf), "lines 1-20");
  assert.equal(pdf.url, undefined); // javascript: dropped
  assert.equal(location(pdf), "p. 3");
  assert.equal(safeUrl("data:text/html,x"), undefined);
  assert.equal(safeUrl("http://x.example/a"), "http://x.example/a");
  assert.deepEqual(citations({ nothing: true }), []);
});

test("graph entities", () => {
  const raw = { results: [], entities: [{ name: "ledger", type: "service", source: "s" }, { type: "x" }] };
  assert.deepEqual(graphEntities(raw), [{ name: "ledger", type: "service", source: "s" }]);
});

test("identity from whoami", () => {
  const me = identity({
    oid: "o",
    upn: "dev@example.com",
    name: "Dev",
    groups: ["eng-all", "payments-devs"],
    app_roles: [],
    policy: { teams: ["payments"], roles: { developer: {}, viewer: {} } },
  });
  assert.deepEqual(me, {
    name: "Dev",
    upn: "dev@example.com",
    groups: ["eng-all", "payments-devs"],
    appRoles: [],
    teams: ["payments"],
    roles: ["developer", "viewer"],
  });
  assert.equal(identity({ hello: 1 }), null);
});
