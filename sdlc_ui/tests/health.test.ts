import assert from "node:assert/strict";
import { test } from "node:test";

import { health, SERVICE } from "../lib/health.ts";

test("health names the service", () => {
  assert.deepEqual(health(), { service: SERVICE, status: "ok" });
});
