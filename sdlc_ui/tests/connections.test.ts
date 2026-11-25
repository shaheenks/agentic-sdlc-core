import assert from "node:assert/strict";
import { test } from "node:test";

import { describeCheck, fieldsFor } from "../lib/connections.ts";

test("each provider's form asks for what it signs in with", () => {
  const jiraCloud = fieldsFor({ name: "Jira Cloud", system: "jira", edition: "cloud" });
  assert.equal(jiraCloud.account?.required, true);
  assert.equal(jiraCloud.baseUrl, null);
  const jiraDc = fieldsFor({ name: "Jira Data Center", system: "jira", edition: "data_center" });
  assert.equal(jiraDc.account, null);
  assert.ok(jiraDc.baseUrl);
  const github = fieldsFor({ name: "GitHub", system: "github", edition: "cloud" });
  assert.equal(github.account, null);
  assert.equal(github.baseUrl, null);
  assert.equal(fieldsFor({ name: "Bitbucket Cloud", system: "bitbucket", edition: "cloud" }).account?.required, false);
  assert.ok(fieldsFor({ name: "GitHub Enterprise Server", system: "github", edition: "data_center" }).baseUrl);
});

test("a check reads as one line", () => {
  assert.equal(describeCheck({ status: "ok", account: "ada" }), "Signed in as ada");
  assert.equal(describeCheck({ status: "refused", reason: "unauthorized" }), "Refused: the token was not accepted");
  assert.match(describeCheck({ status: "untested", reason: "no site" }), /^Not checked: no site$/);
});
