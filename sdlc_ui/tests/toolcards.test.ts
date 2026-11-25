import assert from "node:assert/strict";
import { test } from "node:test";

import { toolCard } from "../lib/toolcards.ts";

test("a knowledge search card says what was asked and keeps the results to inspect", () => {
  const result = JSON.stringify({
    results: [
      { path: "spec/a.md", link: "https://github.com/o/r/blob/main/spec/a.md", source_id: "platform-spec", lines: [3, 9], heading: "Scope", text: "Some   text", score: 0.81234 },
      { path: "x.md", link: "javascript:alert(1)", source_id: "s", text: "t" },
    ],
  });
  const card = toolCard("knowledge_search", { query: "refunds", mode: "hybrid" }, "complete", result);
  assert.equal(card.kind, "knowledge");
  assert.equal(card.label, "Searched knowledge (hybrid)");
  assert.equal(card.detail, "“refunds” · 2 results");
  assert.equal(card.hits?.[0].lines, "3–9");
  assert.equal(card.hits?.[0].snippet, "Some text");
  assert.equal(card.hits?.[1].link, undefined); // only https links
  assert.equal(toolCard("knowledge_search", { query: "q" }, "inProgress", undefined).status, "running");
});

test("a graph card counts nodes and links", () => {
  const result = JSON.stringify({ seeds: ["e1"], nodes: [{ name: "Refund", kind: "concept", source_id: "s" }], edges: [{}, {}] });
  const card = toolCard("knowledge_graph", { name: "Refund" }, "complete", result);
  assert.equal(card.detail, "“Refund” · 1 nodes, 2 links");
});

test("a workflow card shows its outcome; a stopped one says why", () => {
  const done = toolCard("publish_feature", { team: "payments" }, "complete", JSON.stringify({ status: "done", feature: { key: "TAS-1" }, stories: ["TAS-2"] }));
  assert.equal(done.label, "Add to Jira");
  assert.deepEqual(done.facts?.slice(-2), [["Jira feature", "TAS-1"], ["Stories", "TAS-2"]]);
  const stopped = toolCard("features_and_stories", {}, "complete", JSON.stringify({ status: "stopped", reason: "the user kept the chat's team" }));
  assert.equal(stopped.status, "stopped");
  assert.ok(stopped.facts?.some(([k]) => k === "Reason"));
});

test("a refused tool call shows its error", () => {
  const card = toolCard("jira_create_feature", { control_id: "F-1" }, "complete", JSON.stringify({ error: "not_approved", message: "merge it first" }));
  assert.equal(card.status, "failed");
  assert.equal(card.error, "not_approved: merge it first");
  assert.equal(card.label, "Created Jira issues");
});
