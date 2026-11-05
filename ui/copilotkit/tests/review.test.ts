import assert from "node:assert/strict";
import { test } from "node:test";

import {
  attachmentMessage,
  cleanComments,
  lineLabel,
  MAX_COMMENT_CHARS,
  selectLines,
} from "../lib/review.ts";

const doc = { id: "0b9f3c8e-1d2a-4c5b-9e7f-112233445566", name: "stories.md" };

test("line selection: click selects one line, shift extends from the anchor", () => {
  assert.deepEqual(selectLines(null, 4, true), { start: 4, end: 4 });
  assert.deepEqual(selectLines({ start: 4, end: 4 }, 9, true), { start: 4, end: 9 });
  assert.deepEqual(selectLines({ start: 4, end: 9 }, 2, true), { start: 2, end: 4 });
  assert.deepEqual(selectLines({ start: 4, end: 9 }, 7, false), { start: 7, end: 7 });
  assert.equal(lineLabel({ start: 3, end: 3 }), "Line 3");
  assert.equal(lineLabel({ start: 3, end: 5 }), "Lines 3–5");
});

test("comments are trimmed, capped, sorted and empty ones dropped", () => {
  const out = cleanComments([
    { start: 9, end: 9, text: "  later  " },
    { start: 2, end: 3, text: "x".repeat(MAX_COMMENT_CHARS + 50) },
    { start: 5, end: 5, text: "   " },
  ]);
  assert.deepEqual(
    out.map((c) => [c.start, c.text.length]),
    [
      [2, MAX_COMMENT_CHARS],
      [9, 5],
    ],
  );
});

test("attachment message: reference and comments, never the document text", () => {
  const msg = attachmentMessage(doc, [
    { start: 5, end: 5, text: "Add an acceptance criterion\nfor timeouts" },
    { start: 1, end: 2, text: "Shorter title" },
  ]);
  assert.match(msg, /^Attached saved document "stories.md" \(artifact_id: 0b9f3c8e-/);
  assert.match(msg, /read_artifact/);
  assert.ok(msg.indexOf("Lines 1–2: Shorter title") < msg.indexOf("Line 5: Add"));
  assert.match(msg, /Line 5: Add an acceptance criterion\n {2}for timeouts/);
});

test("attachment message without comments, custom request, odd names", () => {
  const msg = attachmentMessage({ ...doc, name: 'a"b`\nc.md' }, [], "Summarise it.");
  assert.equal(msg, `Attached saved document "a b  c.md" (artifact_id: ${doc.id}).\nSummarise it.`);
  assert.throws(() => attachmentMessage({ id: "../x", name: "a.md" }, []));
});
