// Parsing MCP tool results for display (no React, no I/O: unit-tested in tests/results.test.ts).
//
// A tool result reaches the browser as a string. Depending on the layers in between it is the
// tool's JSON object itself, an MCP CallToolResult ({structuredContent} or {content:[{text}]}),
// or ADK's {"result": ...} wrapper. `toolPayload` unwraps all of them.
// Everything here is display data: authorization already happened in the MCP server.

export type Citation = {
  source: string;
  path: string;
  title?: string;
  url?: string; // only http(s) URLs are kept (no javascript: or data: links)
  lines?: [number, number];
  pages?: [number, number];
  heading?: string;
  snippet: string;
  score?: number;
  via?: string; // "vector" | "keyword" | "both" (P11) | "graph" (graph_query)
};

export type GraphEntity = { name: string; type: string; source: string };

export type Identity = {
  name?: string;
  upn?: string;
  groups: string[];
  appRoles: string[];
  teams: string[];
  roles: string[];
};

type Json = Record<string, unknown>;

const isObject = (v: unknown): v is Json => typeof v === "object" && v !== null && !Array.isArray(v);

function parseMaybe(value: unknown): unknown {
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

/** The tool's own JSON object, whatever envelope it arrived in; null if there is none. */
export function toolPayload(raw: unknown, depth = 0): Json | null {
  const value = parseMaybe(raw);
  if (!isObject(value) || depth > 4) return null;
  if (isObject(value.structuredContent)) return toolPayload(value.structuredContent, depth + 1);
  if (Array.isArray(value.content)) {
    const text = value.content.find((c) => isObject(c) && typeof c.text === "string") as
      | Json
      | undefined;
    if (text) return toolPayload(text.text, depth + 1);
  }
  if ("result" in value && Object.keys(value).length === 1) return toolPayload(value.result, depth + 1);
  return value;
}

export function safeUrl(url: unknown): string | undefined {
  if (typeof url !== "string") return undefined;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.toString() : undefined;
  } catch {
    return undefined;
  }
}

function span(value: unknown): [number, number] | undefined {
  return Array.isArray(value) && value.length === 2 && value.every((n) => typeof n === "number")
    ? [value[0], value[1]]
    : undefined;
}

const str = (v: unknown): string | undefined => (typeof v === "string" && v ? v : undefined);

/** search_knowledge / graph_query results -> citations. */
export function citations(raw: unknown): Citation[] {
  const payload = toolPayload(raw);
  if (!payload || !Array.isArray(payload.results)) return [];
  return payload.results.filter(isObject).map((r) => ({
    source: str(r.source) ?? "",
    path: str(r.path) ?? "",
    title: str(r.title),
    url: safeUrl(r.url),
    lines: span(r.lines),
    pages: span(r.pages),
    heading: str(r.heading),
    snippet: str(r.snippet) ?? "",
    score: typeof r.score === "number" ? r.score : undefined,
    via: str(r.via),
  }));
}

export function graphEntities(raw: unknown): GraphEntity[] {
  const payload = toolPayload(raw);
  if (!payload || !Array.isArray(payload.entities)) return [];
  return payload.entities
    .filter(isObject)
    .map((e) => ({ name: str(e.name) ?? "", type: str(e.type) ?? "", source: str(e.source) ?? "" }))
    .filter((e) => e.name);
}

const strings = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];

/** whoami -> identity panel (teams/roles only with explain=true). */
export function identity(raw: unknown): Identity | null {
  const payload = toolPayload(raw);
  if (!payload || !("oid" in payload)) return null;
  const policy = isObject(payload.policy) ? payload.policy : {};
  const names = (v: unknown) =>
    Array.isArray(v)
      ? v.map((x) => (isObject(x) ? str(x.name) ?? str(x.team) ?? str(x.role) : str(x))).filter(
          (x): x is string => Boolean(x),
        )
      : isObject(v)
        ? Object.keys(v)
        : [];
  return {
    name: str(payload.name),
    upn: str(payload.upn),
    groups: strings(payload.groups),
    appRoles: strings(payload.app_roles),
    teams: names(policy.teams),
    roles: names(policy.roles),
  };
}

/** "lines 10-20" / "p. 3" / "pp. 3-5" for a citation. */
export function location(c: Citation): string {
  if (c.pages) return c.pages[0] === c.pages[1] ? `p. ${c.pages[0]}` : `pp. ${c.pages[0]}-${c.pages[1]}`;
  if (c.lines) return `lines ${c.lines[0]}-${c.lines[1]}`;
  return "";
}

/** One chip per cited document (version-02 chat UX): the compact line above the details. */
export type DocumentChip = {
  key: string;
  label: string; // document title, else the file name
  url?: string; // the first http(s) link among the document's hits
  tooltip: string; // "source · path · lines 1-20, p. 3 · via graph"
  hits: number;
};

const CHIP_LABEL_CHARS = 40;

function fileName(path: string): string {
  const parts = path.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? path;
}

/** Citations grouped by document (source + path), in result order. */
export function documentChips(items: Citation[]): DocumentChip[] {
  const byDoc = new Map<string, { first: Citation; url?: string; locations: string[]; hits: number; graph: boolean }>();
  for (const c of items) {
    const key = `${c.source}\u0000${c.path}`;
    const doc = byDoc.get(key) ?? { first: c, locations: [], hits: 0, graph: false };
    doc.hits += 1;
    doc.url ??= c.url;
    doc.graph ||= c.via === "graph";
    const where = location(c);
    if (where && !doc.locations.includes(where)) doc.locations.push(where);
    byDoc.set(key, doc);
  }
  return [...byDoc.entries()].map(([key, doc]) => {
    const name = doc.first.title ?? fileName(doc.first.path) ?? doc.first.source;
    const label = name.length > CHIP_LABEL_CHARS ? `${name.slice(0, CHIP_LABEL_CHARS - 1)}…` : name;
    const tooltip = [doc.first.source, doc.first.path, doc.locations.join(", "), doc.graph ? "via graph" : ""]
      .filter(Boolean)
      .join(" · ");
    return { key, label, url: doc.url, tooltip, hits: doc.hits };
  });
}

// Saved documents (version-03 P5): save_artifact returns one, list_artifacts a list. The download
// link is built here from the id alone (a UUID), never taken from the result, so a tool result
// cannot point the link anywhere but this app's own /artifacts/ API (oauth2-proxy -> MCP server).
export type SavedArtifact = {
  id: string; // the document's stable id (all versions)
  name: string;
  version: number;
  versions: number;
  sizeBytes: number;
  expiresAt: string;
  href: string; // latest version
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

function artifact(value: unknown): SavedArtifact | null {
  if (!isObject(value) || typeof value.id !== "string" || !UUID.test(value.id)) return null;
  return {
    id: value.id,
    name: typeof value.name === "string" ? value.name : "document",
    version: typeof value.version === "number" && value.version >= 1 ? value.version : 1,
    versions: typeof value.versions === "number" && value.versions >= 1 ? value.versions : 1,
    sizeBytes: typeof value.size_bytes === "number" ? value.size_bytes : 0,
    expiresAt: typeof value.expires_at === "string" ? value.expires_at : "",
    href: `/artifacts/${value.id}`,
  };
}

export function savedArtifacts(raw: unknown): SavedArtifact[] {
  const payload = toolPayload(raw);
  if (!payload) return [];
  const items = Array.isArray(payload.artifacts) ? payload.artifacts : [payload];
  return items.map(artifact).filter((a): a is SavedArtifact => a !== null);
}

// Goldfish reviews (version-03 P10): goldfish_review returns lens outcomes and findings grouped by
// severity. All text is reviewer model output (untrusted): shown as plain text only, never linked.
export type Severity = "blocker" | "major" | "nit";
export const SEVERITIES: Severity[] = ["blocker", "major", "nit"];

export type ReviewFinding = {
  severity: Severity;
  title: string;
  detail?: string;
  where?: string;
  suggestion?: string;
  lenses: string[];
};

export type LensOutcome = { lens: string; status: "ok" | "unavailable" | "failed"; findings: number };

export type GoldfishReview = {
  lenses: LensOutcome[];
  findings: ReviewFinding[]; // blockers first, then major, then nits
  counts: Record<Severity, number>;
  summary?: string;
  error?: string;
};

const LENS_STATUS = new Set(["ok", "unavailable", "failed"]);

export function goldfishReview(raw: unknown): GoldfishReview | null {
  const payload = toolPayload(raw);
  if (!payload) return null;
  const counts = { blocker: 0, major: 0, nit: 0 };
  if (typeof payload.error === "string") return { lenses: [], findings: [], counts, error: payload.error };
  if (!Array.isArray(payload.lenses)) return null;
  const lenses = payload.lenses.flatMap((l): LensOutcome[] =>
    isObject(l) && typeof l.lens === "string" && LENS_STATUS.has(String(l.status))
      ? [{ lens: l.lens, status: l.status as LensOutcome["status"], findings: typeof l.findings === "number" ? l.findings : 0 }]
      : [],
  );
  const grouped = isObject(payload.findings) ? payload.findings : {};
  const findings = SEVERITIES.flatMap((severity) =>
    (Array.isArray(grouped[severity]) ? grouped[severity] : []).flatMap((f): ReviewFinding[] =>
      isObject(f) && str(f.title)
        ? [
            {
              severity,
              title: String(f.title),
              detail: str(f.detail),
              where: str(f.where),
              suggestion: str(f.suggestion),
              lenses: strings(f.lenses),
            },
          ]
        : [],
    ),
  );
  for (const f of findings) counts[f.severity] += 1;
  return { lenses, findings, counts, summary: str(payload.summary) };
}

// Active team (version-03 P10 G9): set_active_team locks one of the user's teams for the
// conversation's document once the brief is confirmed. Display only; the team grants nothing.
export type ActiveTeam = { status: "set" | "cleared" | "error"; team?: string; description?: string; error?: string };

export function activeTeam(raw: unknown): ActiveTeam | null {
  const payload = toolPayload(raw);
  if (!payload) return null;
  if (payload.status === "set" && str(payload.team)) {
    return { status: "set", team: String(payload.team), description: str(payload.description) };
  }
  if (payload.status === "cleared") return { status: "cleared" };
  if (payload.status === "error") return { status: "error", error: str(payload.error) ?? "failed" };
  return null;
}
