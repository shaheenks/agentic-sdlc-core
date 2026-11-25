import assert from "node:assert/strict";
import { test } from "node:test";

import { RunClock, seconds } from "../lib/timing.ts";

test("messages of a turn show their time after the user's message, the last one the total", () => {
  const clock = new RunClock();
  clock.observe(["old"], false, 0); // history: not timed
  clock.observe(["old", "u1"], true, 1_000); // the user sends; the run starts
  clock.observe(["old", "u1", "a1"], true, 3_400);
  clock.observe(["old", "u1", "a1", "a2"], true, 9_000);
  clock.observe(["old", "u1", "a1", "a2"], false, 10_800); // the run ends
  assert.equal(clock.label("old", true), "");
  assert.equal(clock.label("a1", false), "+2.4 s");
  assert.equal(clock.label("a2", true), "+8.0 s · total 9.8 s");
});

test("seconds read naturally", () => {
  assert.equal(seconds(950), "0.9 s");
  assert.equal(seconds(12_400), "12 s");
  assert.equal(seconds(125_000), "2 min 5 s");
});
