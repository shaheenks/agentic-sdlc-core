// What a tool call's card shows (FR-AGT-005): one line for every call, and, for knowledge queries, the results
// to inspect on request. No React: unit-tested in tests/toolcards.test.ts.

export type Kind = "knowledge" | "workflow" | "tool";
export type Status = "running" | "done" | "failed" | "stopped";

export type SearchHit = { path: string; link?: string; source: string; lines?: string; heading?: string; snippet: string; score?: number };
export type GraphNode = { name: string; kind: string; path?: string; source: string };

export type Card = {
  kind: Kind;
  label: string; // what was done, in a few words
  detail: string; // the call's main argument or outcome
  status: Status;
  error?: string;
  hits?: SearchHit[];
  graph?: { seeds: string[]; nodes: GraphNode[]; edges: number };
  facts?: [string, string][]; // a workflow's or tool's outcome, as label/value pairs
};

const WORKFLOWS: Record<string, string> = {
  features_and_stories: "Features and stories",
  design_specification: "Design specification",
  publish_feature: "Add to Jira",
  hand_off_design: "Hand off the design",
};

const LABELS: Record<string, string> = {
  whoami: "Checked who you are",
  team_systems: "Read the team's systems",
  artifact_list: "Listed your artifacts",
  artifact_read: "Read an artifact",
  artifact_save: "Saved an artifact",
  artifact_delete: "Deleted an artifact",
  connection_list: "Listed your connections",
  connection_start: "Prepared a connection",
  connection_test: "Tested a connection",
  connection_revoke: "Removed a connection",
  jira_get_issue: "Read a Jira issue",
  jira_search: "Searched Jira",
  jira_create_feature: "Created Jira issues",
  jira_link_design: "Linked the design in Jira",
  repo_list: "Listed a repository folder",
  repo_read_file: "Read a repository file",
  control_publish: "Opened a pull request on the control repository",
  control_status: "Checked the control repository",
};

type Json = Record<string, unknown>;

export function parseResult(result: unknown): Json | null {
  if (result === undefined || result === null || result === "") return null;
  if (typeof result === "object") return result as Json;
  try {
    const parsed = JSON.parse(String(result));
    return parsed && typeof parsed === "object" ? (parsed as Json) : { value: parsed };
  } catch {
    return { value: String(result) };
  }
}

const str = (v: unknown) => (typeof v === "string" ? v : v === undefined || v === null ? "" : JSON.stringify(v));
const clip = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

function mainArgument(name: string, args: Json): string {
  for (const key of ["query", "name", "entity", "key", "text", "path", "repo", "control_id", "jira_key", "provider", "team"]) {
    if (typeof args[key] === "string" && args[key]) return clip(String(args[key]), 80);
  }
  if (name === "jira_create_feature") return clip(str((args.feature as Json | undefined)?.summary), 80);
  return "";
}

export function toolCard(name: string, parameters: unknown, status: string, result: unknown): Card {
  const args = (parameters && typeof parameters === "object" ? parameters : {}) as Json;
  const out = parseResult(result);
  const running = status !== "complete";
  const error = out && typeof out.error === "string" ? `${out.error}${out.message ? `: ${str(out.message)}` : ""}` : undefined;
  const base = { status: (running ? "running" : error ? "failed" : "done") as Status, ...(error ? { error } : {}) };

  if (name === "knowledge_search") {
    const results = Array.isArray(out?.results) ? (out?.results as Json[]) : [];
    const hits = results.map((r) => ({
      path: str(r.path),
      link: typeof r.link === "string" && /^https:\/\//.test(r.link) ? r.link : undefined,
      source: str(r.source_id),
      lines: Array.isArray(r.lines) ? (r.lines as unknown[]).join("–") : undefined,
      heading: typeof r.heading === "string" && r.heading ? r.heading : undefined,
      snippet: clip(str(r.text).replace(/\s+/g, " ").trim(), 240),
      score: typeof r.score === "number" ? r.score : undefined,
    }));
    const mode = typeof args.mode === "string" ? ` (${args.mode})` : "";
    return {
      kind: "knowledge",
      label: running ? "Searching knowledge" : `Searched knowledge${mode}`,
      detail: `“${mainArgument(name, args)}”${running || error ? "" : ` · ${hits.length} result${hits.length === 1 ? "" : "s"}`}`,
      hits,
      ...base,
    };
  }
  if (name === "knowledge_graph") {
    const nodes = (Array.isArray(out?.nodes) ? (out?.nodes as Json[]) : []).map((n) => ({
      name: str(n.name),
      kind: str(n.kind),
      path: typeof n.path === "string" && n.path ? n.path : undefined,
      source: str(n.source_id),
    }));
    const edges = Array.isArray(out?.edges) ? (out?.edges as unknown[]).length : 0;
    const seeds = Array.isArray(out?.seeds) ? (out?.seeds as unknown[]).map(str) : [];
    return {
      kind: "knowledge",
      label: running ? "Exploring the knowledge graph" : "Explored the knowledge graph",
      detail: `“${mainArgument(name, args)}”${running || error ? "" : ` · ${nodes.length} nodes, ${edges} links`}`,
      graph: { seeds, nodes, edges },
      ...base,
    };
  }
  if (name in WORKFLOWS) {
    const outcome = str(out?.status);
    const stopped = outcome === "stopped";
    const facts: [string, string][] = [];
    for (const [key, label] of [
      ["team", "Team"],
      ["rounds", "Review rounds"],
      ["control_id", "Control ID"],
      ["jira_key", "Jira feature"],
      ["approved_by", "Approved by"],
      ["jira_feature_linked", "Linked to"],
      ["reason", "Reason"],
    ] as const) {
      if (out && out[key] !== undefined && out[key] !== null && out[key] !== "") facts.push([label, str(out[key])]);
    }
    const feature = out?.feature as Json | undefined;
    if (feature && typeof feature.key === "string") facts.push(["Jira feature", feature.key]);
    if (Array.isArray(out?.stories) && (out?.stories as unknown[]).every((s) => typeof s === "string")) {
      facts.push(["Stories", (out?.stories as string[]).join(", ")]);
    }
    if (Array.isArray(out?.open_findings) && (out?.open_findings as unknown[]).length) {
      facts.push(["Open findings", String((out?.open_findings as unknown[]).length)]);
    }
    return {
      kind: "workflow",
      label: WORKFLOWS[name],
      detail: running ? "running…" : stopped ? "stopped" : error ? "failed" : outcome.replace(/_/g, " ") || "done",
      facts,
      status: running ? "running" : stopped ? "stopped" : error ? "failed" : "done",
      ...(error ? { error } : {}),
    };
  }
  const facts: [string, string][] = out
    ? Object.entries(out)
        .filter(([k, v]) => k !== "error" && k !== "message" && (typeof v === "string" || typeof v === "number" || typeof v === "boolean"))
        .slice(0, 6)
        .map(([k, v]) => [k.replace(/_/g, " "), clip(String(v), 120)])
    : [];
  return { kind: "tool", label: LABELS[name] ?? name.replace(/_/g, " "), detail: mainArgument(name, args), facts, ...base };
}
