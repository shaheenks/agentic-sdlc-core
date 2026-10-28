"use client";

// How MCP tool calls appear in the chat (version-01 M5). Rendering only: no frontend tools, no new
// data paths. Every value comes from a tool result the MCP server already authorized; React
// escapes text, and links are limited to http(s) (lib/results.ts safeUrl).

import { defineToolCallRenderer } from "@copilotkit/react-core/v2";
import { z } from "zod";

import {
  type Citation,
  citations,
  graphEntities,
  identity,
  location,
  safeUrl,
  toolPayload,
} from "@/lib/results";

const done = (status: unknown) => String(status).toLowerCase() === "complete";

function Pending({ label }: { label: string }) {
  return <div className="tool pending">{label}…</div>;
}

function CitationCard({ c }: { c: Citation }) {
  const heading = c.title ?? c.path;
  return (
    <li className="citation">
      <div className="citation-head">
        {c.url ? (
          <a href={c.url} target="_blank" rel="noopener noreferrer">
            {heading}
          </a>
        ) : (
          <span>{heading}</span>
        )}
        {c.via === "graph" && <span className="badge">via graph</span>}
      </div>
      <div className="citation-meta">
        <span>{c.source}</span>
        {c.title && <span>{c.path}</span>}
        {location(c) && <span>{location(c)}</span>}
        {c.heading && <span>§ {c.heading}</span>}
      </div>
      <p className="citation-snippet">{c.snippet.length > 280 ? `${c.snippet.slice(0, 280)}…` : c.snippet}</p>
    </li>
  );
}

function Citations({ result, label }: { result: unknown; label: string }) {
  const items = citations(result);
  if (!items.length) return <div className="tool">{label}: no matching knowledge you can read.</div>;
  return (
    <div className="tool">
      <div className="tool-title">
        {label} · {items.length} source{items.length === 1 ? "" : "s"}
      </div>
      <ol className="citations">
        {items.map((c, i) => (
          <CitationCard key={`${c.source}:${c.path}:${i}`} c={c} />
        ))}
      </ol>
    </div>
  );
}

// Tools that read with the user's own account (version-01 M6)
function ConnectedResult({ result, label }: { result: unknown; label: string }) {
  const payload = toolPayload(result);
  if (!payload) return null;
  if (payload.connected === false) {
    return (
      <div className="tool">
        <div className="tool-title">{label}: account not connected</div>
        <div>{String(payload.reason ?? "")}</div>
        <a href="/chat/connections">Connect your account</a>
      </div>
    );
  }
  const title = String(payload.title ?? payload.summary ?? payload.path ?? payload.key ?? label);
  const url = safeUrl(payload.url);
  return (
    <div className="tool">
      <div className="tool-title">
        {label}:{" "}
        {url ? (
          <a href={url} target="_blank" rel="noopener noreferrer">
            {title}
          </a>
        ) : (
          title
        )}
      </div>
      <div className="citation-meta">
        <span>with your {String(payload.connection ?? "")} account</span>
        {payload.truncated === true && <span>truncated</span>}
      </div>
    </div>
  );
}

const connectedRenderer = (name: string, label: string) =>
  defineToolCallRenderer({
    name,
    args: z.object({}).passthrough(),
    render: ({ status, result }) =>
      done(status) ? <ConnectedResult result={result} label={label} /> : <Pending label={label} />,
  });

const searchArgs = z.object({ query: z.string().optional(), k: z.number().optional() });
const graphArgs = searchArgs.extend({ hops: z.number().optional() });
const whoamiArgs = z.object({ explain: z.boolean().optional() });

export const toolRenderers = [
  connectedRenderer("jira_get_issue", "Jira issue"),
  connectedRenderer("confluence_get_page", "Confluence page"),
  connectedRenderer("github_get_file", "GitHub file"),
  connectedRenderer("bitbucket_get_file", "Bitbucket file"),
  defineToolCallRenderer({
    name: "search_knowledge",
    args: searchArgs,
    render: ({ status, args, result }) =>
      done(status) ? (
        <Citations result={result} label={`Searched “${args.query ?? ""}”`} />
      ) : (
        <Pending label="Searching knowledge" />
      ),
  }),
  defineToolCallRenderer({
    name: "graph_query",
    args: graphArgs,
    render: ({ status, args, result }) => {
      if (!done(status)) return <Pending label="Querying the knowledge graph" />;
      const entities = graphEntities(result).slice(0, 12);
      return (
        <div>
          <Citations result={result} label={`Graph query “${args.query ?? ""}”`} />
          {entities.length > 0 && (
            <div className="entities">
              {entities.map((e) => (
                <span key={`${e.source}:${e.name}`} className="entity" title={`${e.type} · ${e.source}`}>
                  {e.name}
                </span>
              ))}
            </div>
          )}
        </div>
      );
    },
  }),
  defineToolCallRenderer({
    name: "whoami",
    args: whoamiArgs,
    render: ({ status, result }) => {
      if (!done(status)) return <Pending label="Checking who you are" />;
      const me = identity(result);
      if (!me) return null;
      const row = (label: string, values: string[]) =>
        values.length > 0 && (
          <div className="identity-row">
            <span className="identity-label">{label}</span>
            {values.map((v) => (
              <span key={v} className="entity">
                {v}
              </span>
            ))}
          </div>
        );
      return (
        <div className="tool identity">
          <div className="tool-title">Signed in as {me.name ?? me.upn ?? "you"}</div>
          {row("Teams", me.teams)}
          {row("Roles", me.roles)}
          {row("Groups", me.groups)}
          {row("App roles", me.appRoles)}
        </div>
      );
    },
  }),
];
