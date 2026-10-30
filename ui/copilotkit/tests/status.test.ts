import assert from "node:assert/strict";
import { test } from "node:test";

import { connectionStatuses, initials, overallState, parseMe } from "../lib/status.ts";

const TODAY = new Date("2026-10-30T09:00:00Z");

test("parseMe keeps only name and upn", () => {
  assert.deepEqual(parseMe({ name: "Ana Dev", upn: "ana@example.com", oid: "x", token: "t" }), {
    name: "Ana Dev",
    upn: "ana@example.com",
  });
  assert.equal(parseMe({}), null);
  assert.equal(parseMe(null), null);
  assert.equal(parseMe("nope"), null);
});

test("initials from the name, else the sign-in name", () => {
  assert.equal(initials({ name: "Ana Dev", upn: "" }), "AD");
  assert.equal(initials({ name: "", upn: "paul.smith@example.com" }), "PS");
  assert.equal(initials({ name: "Ben", upn: "" }), "BE");
});

test("connection states for the navbar", () => {
  const body = {
    connections: [
      { id: "github", description: "GitHub.com", connected: true, status: "ok", display: "octo", expires_at: "2026-12-31", expiring_soon: false, token: "never shown" },
      { id: "bitbucket", description: "Bitbucket Cloud", connected: true, status: "ok", expires_at: "2026-11-02", expiring_soon: true },
      { id: "atlassian", description: "Jira and Confluence", connected: true, status: "invalid", expires_at: "2027-01-01" },
      { id: "jira-dc", connected: true, status: "ok", expired: true, expires_at: "2026-10-01" },
      { id: "confluence-dc", description: "Confluence DC", connected: false },
      { description: "no id: dropped" },
    ],
  };
  const statuses = connectionStatuses(body, TODAY);
  assert.deepEqual(
    statuses.map((s) => [s.id, s.state, s.detail]),
    [
      ["github", "ok", "octo · expires 2026-12-31"],
      ["bitbucket", "warn", "token expires in 3 days"],
      ["atlassian", "warn", "token rejected by the provider: connect again"],
      ["jira-dc", "warn", "token expired: connect again"],
      ["confluence-dc", "off", "not connected"],
    ],
  );
  assert.equal(statuses[3].label, "jira-dc"); // no description: the id
  assert.ok(!JSON.stringify(statuses).includes("never shown"));
  assert.equal(overallState(statuses), "warn");
  assert.equal(overallState(statuses.filter((s) => s.state !== "warn")), "ok");
  assert.equal(overallState([statuses[4]]), "off");
  assert.equal(overallState([]), null);
});

test("connections off or unreadable: nothing to show", () => {
  assert.deepEqual(connectionStatuses(null), []);
  assert.deepEqual(connectionStatuses({ detail: "user connections are not configured" }), []);
});
