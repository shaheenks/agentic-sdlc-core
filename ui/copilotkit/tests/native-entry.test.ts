// native-entry.mjs (CH-0016): the paths outside /chat reach the native route handlers.

import assert from "node:assert/strict";
import { test } from "node:test";

// @ts-expect-error plain JavaScript entry point (no types)
import { mapPath } from "../native-entry.mjs";

test("same-origin paths map onto /chat/api/native, the rest is unchanged", () => {
  const cases: [string, string | null][] = [
    ["/", null],
    ["/me", "/chat/api/native/me"],
    ["/threads", "/chat/api/native/threads"],
    ["/threads/t-1", "/chat/api/native/threads/t-1"],
    ["/connections/", "/chat/api/native/mcp/connections/"],
    ["/connections/github", "/chat/api/native/mcp/connections/github"],
    ["/artifacts/", "/chat/api/native/mcp/artifacts/"],
    ["/artifacts/abc/versions", "/chat/api/native/mcp/artifacts/abc/versions"],
    ["/artifacts/abc?version=2", "/chat/api/native/mcp/artifacts/abc?version=2"],
    ["/oauth2/sign_out", "/chat/auth/sign_out"],
    ["/chat/", "/chat/"],
    ["/chat/api/copilotkit/agent/default/run", "/chat/api/copilotkit/agent/default/run"],
    ["/mention", "/mention"],
    ["/dev-ui/", "/dev-ui/"],
  ];
  for (const [from, to] of cases) assert.equal(mapPath(from), to, from);
});
