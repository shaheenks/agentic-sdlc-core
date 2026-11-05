import assert from "node:assert/strict";
import { test } from "node:test";

import {
  citations,
  documentChips,
  graphEntities,
  identity,
  location,
  safeUrl,
  savedArtifacts,
  toolPayload,
} from "../lib/results.ts";

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

test("document chips group hits per document", () => {
  const items = citations({
    results: [
      { source: "payments-code", path: "docs/refunds.md", lines: [1, 9], snippet: "a", url: "https://git.example/r" },
      { source: "payments-code", path: "docs/refunds.md", lines: [20, 30], snippet: "b", via: "graph" },
      { source: "eng-standards", path: "incident-policy.pdf", title: "Incident policy", pages: [3, 3], snippet: "c" },
      { source: "x", path: "dir/" + "y".repeat(60) + ".md", snippet: "d", url: "javascript:alert(1)" },
    ],
  });
  const chips = documentChips(items);
  assert.equal(chips.length, 3);
  assert.deepEqual(
    { label: chips[0].label, url: chips[0].url, hits: chips[0].hits, tooltip: chips[0].tooltip },
    {
      label: "refunds.md",
      url: "https://git.example/r",
      hits: 2,
      tooltip: "payments-code · docs/refunds.md · lines 1-9, lines 20-30 · via graph",
    },
  );
  assert.equal(chips[1].label, "Incident policy"); // title wins over the file name
  assert.equal(chips[1].url, undefined);
  assert.equal(chips[2].label.length, 40);
  assert.ok(chips[2].label.endsWith("…"));
  assert.equal(chips[2].url, undefined); // unsafe link dropped
  assert.deepEqual(documentChips([]), []);
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

test("saved artifacts: links are built from the UUID only", () => {
  const id = "0b9f3c8e-1d2a-4c5b-9e7f-112233445566";
  const saved = { id, name: "stories.md", size_bytes: 12, expires_at: "2026-11-12T00:00:00+00:00", download_path: "https://evil.example/x" };
  assert.deepEqual(savedArtifacts(saved), [
    { id, name: "stories.md", sizeBytes: 12, expiresAt: "2026-11-12T00:00:00+00:00", href: `/artifacts/${id}` },
  ]);
  assert.equal(savedArtifacts({ artifacts: [saved, { id: "../../etc" }] }).length, 1);
  assert.deepEqual(savedArtifacts({ id: "javascript:alert(1)" }), []);
  assert.deepEqual(savedArtifacts("not json"), []);
});
