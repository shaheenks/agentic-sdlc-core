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
  via?: string; // graph_query: "vector" | "graph"
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
