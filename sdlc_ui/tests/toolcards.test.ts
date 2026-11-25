import assert from "node:assert/strict";
import { test } from "node:test";

import { toolCard } from "../lib/toolcards.ts";

const done = (name: string, args: object, result: object) => toolCard(name, args, "complete", JSON.stringify(result));

test("a knowledge search says what was asked, how many hits and from which sources", () => {
  const card = done("knowledge_search", { query: "refund flow" }, {
    results: [
      { path: "spec/a.md", link: "https://github.com/o/r/blob/main/spec/a.md", source_id: "platform-spec", lines: [3, 9], heading: "Scope", text: "Some   text", score: 0.81234 },
      { path: "x.md", link: "javascript:alert(1)", source_id: "tasklist", text: "t" },
    ],
  });
  assert.equal(card.detail, "“refund flow” · 2 results from platform-spec, tasklist");
  assert.equal(card.items?.[0].title, "spec/a.md · lines 3–9");
  assert.equal(card.items?.[0].meta, "platform-spec · Scope · score 0.81");
  assert.equal(card.items?.[1].link, undefined); // only https links
});

test("tools say what they touched and what came of it", () => {
  assert.equal(done("artifact_read", { name: "f.md" }, { name: "f.md", version: 2, content: "# T\nline" }).detail, "f.md · version 2 · 2 lines");
  assert.equal(done("artifact_save", {}, { name: "f.md", version: 3, size: 2048 }).detail, "f.md · version 3 · 2.0 KB");
  const search = done("jira_search", { text: "openapi" }, { issues: [{ key: "TAS-1", summary: "Docs", status: "To Do", issue_type: "Story", url: "https://x.atlassian.net/browse/TAS-1" }] });
  assert.equal(search.detail, "“openapi” · 1 issue");
  assert.equal(search.items?.[0].title, "TAS-1 · Docs");
  assert.equal(done("repo_read_file", { repo: "o/app", path: "a.ts" }, { repo: "o/app", path: "a.ts", content: "a\nb\nc" }).detail, "o/app/a.ts · 3 lines");
  const status = done("control_status", { control_id: "F-1" }, { control_id: "F-1", artifacts: { feature: { approved: true, merged_by: "grace" }, design: { published: false } }, writes: [] });
  assert.deepEqual(status.facts, [["feature", "approved by grace"], ["design", "not published"]]);
});

test("a refused call says why in plain words", () => {
  const card = done("repo_list", { repo: "other/repo", path: "" }, { error: "constraint_denied", message: "that repository is not one of your team's" });
  assert.equal(card.status, "failed");
  assert.match(card.detail, /not one of your team's systems/);
  assert.equal(done("jira_create_feature", {}, { error: "not_approved", message: "x" }).error?.startsWith("not approved yet"), true);
});

test("a workflow card shows its subject while running and its outcome when done", () => {
  const running = toolCard("design_specification", { team: "taskslist", feature: "# OpenAPI docs\n..." }, "executing", undefined);
  assert.equal(running.detail, "OpenAPI docs for taskslist");
  const drafted = done("design_specification", { team: "taskslist" }, { status: "drafted", document: "# OpenAPI design\n\nBody", rounds: 3, open_findings: [] });
  assert.equal(drafted.detail, "drafted “OpenAPI design”");
  assert.ok(drafted.preview?.startsWith("# OpenAPI design"));
  assert.ok(drafted.facts?.some(([k, v]) => k === "Review rounds" && v === "3"));
  const stopped = done("features_and_stories", {}, { status: "stopped", reason: "the user kept the chat's team" });
  assert.equal(stopped.status, "stopped");
  assert.equal(stopped.detail, "stopped: the user kept the chat's team");
  const jira = done("publish_feature", {}, { status: "done", feature: { key: "TAS-1" }, stories: ["TAS-2", "TAS-3"] });
  assert.equal(jira.detail, "created TAS-1 with 2 stories");
});
