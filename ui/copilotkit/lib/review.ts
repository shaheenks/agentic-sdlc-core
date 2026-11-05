// Inline review of a saved document (version-03 P5, F5): line comments drafted in the viewer and
// attached to the conversation as one user message. The message carries a reference (name + id)
// and the comments, never the document text: the agent reads it with read_artifact, as the user,
// authorized and audited by the MCP server. Comments are user text; nothing here is trusted input.

export type LineComment = { start: number; end: number; text: string };

export const MAX_COMMENTS = 50;
export const MAX_COMMENT_CHARS = 1000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function lineLabel(c: { start: number; end: number }): string {
  return c.start === c.end ? `Line ${c.start}` : `Lines ${c.start}–${c.end}`;
}

/** Selection after clicking line `n` (shift = extend the current selection). */
export function selectLines(
  current: { start: number; end: number } | null,
  n: number,
  extend: boolean,
): { start: number; end: number } {
  if (!extend || !current) return { start: n, end: n };
  const anchor = current.start;
  return { start: Math.min(anchor, n), end: Math.max(anchor, n) };
}

/** Comments sorted by position; empty ones dropped, long ones cut, at most MAX_COMMENTS. */
export function cleanComments(comments: LineComment[]): LineComment[] {
  return comments
    .map((c) => ({ ...c, text: c.text.trim().slice(0, MAX_COMMENT_CHARS) }))
    .filter((c) => c.text && c.start >= 1 && c.end >= c.start)
    .sort((a, b) => a.start - b.start || a.end - b.end)
    .slice(0, MAX_COMMENTS);
}

export const DEFAULT_REQUEST =
  "Read it with read_artifact, apply my comments, save the result as the next version of the same document and give me the link.";

/** The chat message that attaches a saved document with its comments. */
export function attachmentMessage(
  artifact: { id: string; name: string; version?: number },
  comments: LineComment[],
  request: string = DEFAULT_REQUEST,
): string {
  if (!UUID.test(artifact.id)) throw new Error("not a saved document id");
  const name = artifact.name.replace(/[\r\n"`]/g, " ").slice(0, 100);
  const v = artifact.version;
  const version = typeof v === "number" && Number.isInteger(v) && v >= 1 ? `, version: ${v}` : "";
  const lines = [`Attached saved document "${name}" (artifact_id: ${artifact.id}${version}).`];
  const ask = request.trim();
  if (ask) lines.push(ask);
  const cleaned = cleanComments(comments);
  if (cleaned.length > 0) {
    lines.push("", "My comments:");
    for (const c of cleaned) {
      // one bullet per comment: newlines inside a comment are indented under its bullet
      lines.push(`- ${lineLabel(c)}: ${c.text.replace(/\r?\n/g, "\n  ")}`);
    }
  }
  return lines.join("\n");
}
