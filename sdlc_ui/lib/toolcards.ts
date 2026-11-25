// What a tool call's card tells the user (FR-AGT-005): one line saying what was done and what came of it, and,
// where there is something to inspect (search hits, issues, files, a workflow's outcome), a collapsed body.
// No React: unit-tested in tests/toolcards.test.ts.

export type Kind = "knowledge" | "workflow" | "tool";
export type Status = "running" | "done" | "failed" | "stopped";
export type Item = { title: string; link?: string; meta?: string; text?: string };

export type Card = {
  kind: Kind;
  label: string; // what was done
  detail: string; // its subject and outcome, in a few words
  status: Status;
  error?: string; // in plain words
  items?: Item[]; // hits, issues, entries, nodes
  facts?: [string, string][];
  preview?: string; // a file's or artifact's first lines
  link?: { href: string; label: string };
};

type Json = Record<string, unknown>;

const WORKFLOWS: Record<string, string> = {
  features_and_stories: "Features and stories",
  design_specification: "Design specification",
  publish_feature: "Add to Jira",
  hand_off_design: "Hand off the design",
};

// error codes from user_agent_mcp and the connectors, in words
const ERRORS: Record<string, string> = {
  constraint_denied: "not one of your team's systems",
  team_run_required: "needs a chat for one of your teams",
  not_connected: "connect this system first (Connections page)",
  not_approved: "not approved yet: the pull request on the control repository must be merged first",
  already_done: "already done",
  partly_done: "partly done earlier",
  downstream_not_found: "not found",
  downstream_unauthorized: "the system did not accept your token",
  downstream_forbidden: "your token lacks the rights for this",
  downstream_invalid: "the system rejected the request",
  downstream_unavailable: "the system could not be reached",
  invalid_argument: "the request was malformed",
  not_found: "not found",
  failed: "the run stopped",
};

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
const https = (v: unknown) => (typeof v === "string" && /^https:\/\//.test(v) ? v : undefined);
const list = (v: unknown) => (Array.isArray(v) ? (v as Json[]) : []);
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const lines = (text: string) => (text ? text.split("\n").length : 0);
const size = (bytes: unknown) => {
  const n = typeof bytes === "number" ? bytes : 0;
  return n < 1024 ? `${n} B` : `${(n / 1024).toFixed(1)} KB`;
};
const firstLines = (text: string, n = 12) => clip(text.split("\n").slice(0, n).join("\n"), 1200);

function errorOf(out: Json | null): string | undefined {
  if (!out || typeof out.error !== "string") return undefined;
  const words = ERRORS[out.error] ?? out.error.replace(/_/g, " ");
  const message = typeof out.message === "string" && out.message ? out.message : "";
  return message && !words.includes(message) ? `${words} (${clip(message, 200)})` : words;
}

function issues(out: Json | null): Item[] {
  return list(out?.issues).map((i) => ({
    title: `${str(i.key)} · ${str(i.summary)}`,
    link: https(i.url),
    meta: [str(i.issue_type), str(i.status)].filter(Boolean).join(" · "),
  }));
}

function knowledge(name: string, args: Json, out: Json | null, running: boolean): Partial<Card> {
  if (name === "knowledge_search") {
    const hits = list(out?.results);
    const sources = [...new Set(hits.map((h) => str(h.source_id)).filter(Boolean))];
    return {
      label: running ? "Searching knowledge" : "Searched knowledge",
      detail: `“${clip(str(args.query), 80)}”${running ? "" : ` · ${plural(hits.length, "result")}${sources.length ? ` from ${sources.join(", ")}` : ""}`}`,
      items: hits.map((h) => ({
        title: `${str(h.path)}${Array.isArray(h.lines) ? ` · lines ${(h.lines as unknown[]).join("–")}` : ""}`,
        link: https(h.link),
        meta: [str(h.source_id), str(h.heading), typeof h.score === "number" ? `score ${h.score.toFixed(2)}` : ""]
          .filter(Boolean)
          .join(" · "),
        text: clip(str(h.text).replace(/\s+/g, " ").trim(), 260),
      })),
    };
  }
  const nodes = list(out?.nodes);
  const edges = list(out?.edges).length;
  return {
    label: running ? "Exploring related knowledge" : "Explored related knowledge",
    detail: `“${clip(str(args.name ?? args.entity), 80)}”${running ? "" : ` · ${plural(nodes.length, "concept")}, ${plural(edges, "link")}`}`,
    items: nodes.slice(0, 40).map((n) => ({
      title: str(n.name),
      meta: [str(n.kind), str(n.path)].filter(Boolean).join(" · "),
      text: clip(str(n.description), 200),
    })),
  };
}

function workflow(name: string, args: Json, out: Json | null, running: boolean): Partial<Card> {
  // the first non-empty line, without a Markdown heading marker
  const firstLine = (v: unknown) =>
    str(v)
      .split("\n")
      .find((l) => l.trim())
      ?.replace(/^#+\s*/, "")
      .trim() ?? "";
  const subject = clip(
    str(args.summary) ||
      str(args.jira_key) ||
      str(args.control_id) ||
      firstLine(args.brief) ||
      firstLine(args.feature) ||
      firstLine(args.content),
    90,
  );
  const team = str(args.team);
  if (running) return { label: WORKFLOWS[name], detail: [subject, team && `for ${team}`].filter(Boolean).join(" ") };
  const outcome = str(out?.status);
  const facts: [string, string][] = [];
  const add = (k: string, v: unknown) => {
    const s = Array.isArray(v) ? (v as unknown[]).map(str).join(", ") : str(v);
    if (s) facts.push([k, s]);
  };
  add("Team", out?.team ?? team);
  add("Review rounds", out?.rounds);
  if (Array.isArray(out?.open_findings)) add("Open findings", (out?.open_findings as unknown[]).length || "none");
  add("Control ID", out?.control_id);
  add("Jira feature", (out?.feature as Json | undefined)?.key ?? out?.jira_key);
  add("Stories", out?.stories);
  add("Approved by", out?.approved_by);
  add("Linked to", out?.jira_feature_linked);
  add("Target repositories", out?.repositories);
  add("Next", out?.next);
  const document = str(out?.document);
  const title = document.split("\n").find((l) => l.trim())?.replace(/^#+\s*/, "") ?? "";
  const pr = (out?.pull_request as Json | undefined)?.url;
  let detail = subject;
  if (outcome === "drafted") detail = `drafted${title ? ` “${clip(title, 70)}”` : ""}`;
  if (outcome === "done") detail = `created ${str((out?.feature as Json | undefined)?.key)} with ${plural(list(out?.stories).length, "story", "stories")}`;
  if (outcome === "handed_off") detail = `handed off ${str(out?.control_id)}`;
  if (outcome === "stopped") detail = `stopped: ${clip(str(out?.reason), 120)}`;
  return {
    label: WORKFLOWS[name],
    detail,
    facts,
    ...(document ? { preview: firstLines(document) } : {}),
    ...(https(pr) ? { link: { href: https(pr) as string, label: "Open the pull request" } } : {}),
    ...(outcome === "stopped" ? { status: "stopped" as Status } : {}),
  };
}

function tool(name: string, args: Json, out: Json | null, running: boolean): Partial<Card> {
  const o = out ?? {};
  switch (name) {
    case "artifact_save":
      return { label: "Saved artifact", detail: running ? str(args.name) : `${str(o.name)} · version ${str(o.version)} · ${size(o.size)}`, link: { href: "/artifacts", label: "Your artifacts" } };
    case "artifact_read": {
      const content = str(o.content);
      return { label: "Read artifact", detail: running ? str(args.name) : `${str(o.name)} · version ${str(o.version)} · ${plural(lines(content), "line")}`, ...(content ? { preview: firstLines(content) } : {}) };
    }
    case "artifact_list": {
      const found = list(o.artifacts);
      return { label: "Listed your artifacts", detail: running ? "" : plural(found.length, "artifact"), items: found.map((a) => ({ title: str(a.name), meta: `version ${str(a.version)} · ${size(a.size)}` })) };
    }
    case "artifact_delete":
      return { label: "Deleted artifact", detail: str(args.name) };
    case "jira_search": {
      const found = issues(out);
      const what = [str(args.text) && `“${clip(str(args.text), 50)}”`, str(args.issue_type), str(args.status)].filter(Boolean).join(", ");
      return { label: "Searched Jira", detail: `${what || "the team's projects"}${running ? "" : ` · ${plural(found.length, "issue")}`}`, items: found };
    }
    case "jira_get_issue": {
      const stories = list(o.stories).map((s) => ({ title: `${str(s.key)} · ${str(s.summary)}`, link: https(s.url), meta: str(s.status) }));
      return {
        label: "Read Jira issue",
        detail: running ? str(args.key) : `${str(o.key)} · ${clip(str(o.summary), 70)}${o.status ? ` · ${str(o.status)}` : ""}`,
        ...(https(o.url) ? { link: { href: https(o.url) as string, label: `Open ${str(o.key)}` } } : {}),
        ...(stories.length ? { items: stories } : {}),
        ...(o.description ? { preview: firstLines(str(o.description), 8) } : {}),
      };
    }
    case "jira_create_feature":
      return {
        label: "Created Jira issues",
        detail: running ? clip(str((args.feature as Json | undefined)?.summary), 70) : `${str((o.feature as Json | undefined)?.key)} with ${plural(list(o.stories).length, "story", "stories")} in ${str(o.project)}`,
        ...(https((o.feature as Json | undefined)?.url) ? { link: { href: https((o.feature as Json).url) as string, label: "Open the feature" } } : {}),
      };
    case "jira_link_design":
      return { label: "Linked the design in Jira", detail: running ? str(args.control_id) : `${str(o.feature)} → design` };
    case "repo_read_file": {
      const content = str(o.content);
      return { label: "Read file", detail: `${str(o.repo || args.repo)}/${str(o.path || args.path)}${running ? "" : ` · ${plural(lines(content), "line")}`}`, ...(content ? { preview: firstLines(content) } : {}) };
    }
    case "repo_list": {
      const entries = list(o.entries);
      return { label: "Listed folder", detail: `${str(o.repo || args.repo)}/${str(o.path ?? args.path)}${running ? "" : ` · ${plural(entries.length, "entry", "entries")}`}`, items: entries.map((e) => ({ title: `${str(e.name)}${e.type === "dir" ? "/" : ""}` })) };
    }
    case "team_systems": {
      const teams = (o.teams ?? {}) as Record<string, Json>;
      const facts: [string, string][] = Object.entries(teams).flatMap(([team, s]) => [
        [`${team}: Jira`, list(s.jira).map((j) => str(j.project)).join(", ") || "none"],
        [`${team}: repositories`, list(s.repositories).map((r) => str(r.repo)).join(", ") || "none"],
        [`${team}: control repository`, str((s.control_repo as Json | undefined)?.repo) || "none"],
      ] as [string, string][]);
      return { label: "Read the team's systems", detail: Object.keys(teams).join(", "), facts };
    }
    case "control_publish": {
      const pr = o.pull_request as Json | undefined;
      return { label: "Opened a pull request for approval", detail: running ? str(args.kind) : `${str(o.kind)} of ${str(o.control_id)} on the control repository`, ...(https(pr?.url) ? { link: { href: https(pr?.url) as string, label: "Open the pull request" } } : {}) };
    }
    case "control_status": {
      const artifacts = (o.artifacts ?? {}) as Record<string, Json>;
      const facts = Object.entries(artifacts).map(([kind, a]) => [
        kind,
        a.approved ? `approved${a.merged_by ? ` by ${str(a.merged_by)}` : ""}` : a.published ? "published, not approved" : "not published",
      ]) as [string, string][];
      for (const w of list(o.writes)) facts.push([str(w.action).replace(/_/g, " "), str((w.results as Json | undefined)?.feature) || str(w.error)]);
      return { label: "Checked the control repository", detail: str(o.control_id || args.control_id || args.jira_key), facts };
    }
    case "whoami": {
      const teams = Object.keys((o.teams ?? {}) as Json);
      return { label: "Checked who you are", detail: [str(o.email), teams.length ? `teams: ${teams.join(", ")}` : ""].filter(Boolean).join(" · ") };
    }
    case "connection_test":
      return { label: "Tested connection", detail: `${str(o.provider || args.provider)}${o.status === "ok" ? ` · signed in as ${str(o.account)}` : o.status ? ` · ${str(o.status)}` : ""}` };
    case "connection_list":
      return { label: "Listed your connections", detail: list(o.connections).map((c) => str(c.provider)).join(", ") || (running ? "" : "none") };
    case "connection_start":
      return { label: "Prepared a connection", detail: str(o.name || args.provider), ...(https(o.entry_url) ? { link: { href: https(o.entry_url) as string, label: "Enter the token" } } : {}) };
    default:
      return { label: name.replace(/_/g, " "), detail: "" };
  }
}

export function toolCard(name: string, parameters: unknown, status: string, result: unknown): Card {
  const args = (parameters && typeof parameters === "object" ? parameters : {}) as Json;
  const out = parseResult(result);
  const running = status !== "complete";
  const error = running ? undefined : errorOf(out);
  const kind: Kind = name.startsWith("knowledge_") ? "knowledge" : name in WORKFLOWS ? "workflow" : "tool";
  const body = kind === "knowledge" ? knowledge(name, args, out, running) : kind === "workflow" ? workflow(name, args, out, running) : tool(name, args, out, running);
  return {
    kind,
    label: body.label ?? name,
    detail: error ? `${body.detail ? `${body.detail} · ` : ""}${error}` : (body.detail ?? ""),
    status: running ? "running" : error ? "failed" : (body.status ?? "done"),
    ...(error ? { error } : {}),
    ...(body.items?.length ? { items: body.items } : {}),
    ...(body.facts?.length ? { facts: body.facts } : {}),
    ...(body.preview && !error ? { preview: body.preview } : {}),
    ...(body.link && !error ? { link: body.link } : {}),
  };
}
