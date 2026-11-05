"use client";

// How MCP tool calls appear in the chat (version-01 M5). Rendering only: no frontend tools, no new
// data paths. Every value comes from a tool result the MCP server already authorized; React
// escapes text, and links are limited to http(s) (lib/results.ts safeUrl).

import { defineToolCallRenderer } from "@copilotkit/react-core/v2";
import { type ReactNode, useEffect, useState } from "react";
import { z } from "zod";

import { ARTIFACTS_CHANGED } from "@/components/ArtifactsPanel";
import { openArtifact } from "@/components/ArtifactViewer";
import {
  type Citation,
  citations,
  type DocumentChip,
  documentChips,
  graphEntities,
  identity,
  location,
  safeUrl,
  savedArtifacts,
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

const MAX_CHIPS = 6;

function DocChip({ chip }: { chip: DocumentChip }) {
  const text = chip.hits > 1 ? `${chip.label} ×${chip.hits}` : chip.label;
  return chip.url ? (
    <a
      className="chip"
      href={chip.url}
      target="_blank"
      rel="noopener noreferrer"
      title={chip.tooltip}
      onClick={(e) => e.stopPropagation()}
    >
      {text}
      <span className="chip-icon" aria-hidden="true">
        ↗
      </span>
    </a>
  ) : (
    <span className="chip" title={chip.tooltip}>
      {text}
    </span>
  );
}

// A compact tool card (version-02 chat UX): one thin line; clicking the card expands the body,
// clicking the line collapses it (keyboard: Enter/Space). Links in the line stop propagation, so
// they open without toggling.
function CompactCard({ line, children }: { line: ReactNode; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const toggle = () => setOpen((v) => !v);
  return (
    <div
      className="tool compact clickable"
      role="button"
      tabIndex={0}
      aria-expanded={open}
      onClick={() => !open && setOpen(true)}
      onKeyDown={(e) => {
        if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          toggle();
        }
      }}
    >
      <div
        className="tool-line"
        onClick={(e) => {
          e.stopPropagation();
          toggle();
        }}
      >
        {line}
        <span className="tool-toggle" aria-hidden="true">
          {open ? "▴" : "▾"}
        </span>
      </div>
      {open && (
        <div className="tool-body" onClick={(e) => e.stopPropagation()}>
          {children}
        </div>
      )}
    </div>
  );
}

// Search results: small document chips in the line; the full cards with snippets (and graph
// entities) in the body.
function Citations({ result, label, children }: { result: unknown; label: string; children?: ReactNode }) {
  const items = citations(result);
  if (!items.length) return <div className="tool compact">{label}: no matching knowledge you can read.</div>;
  const chips = documentChips(items);
  const hidden = chips.length - MAX_CHIPS;
  return (
    <CompactCard
      line={
        <>
          <span className="tool-label" title={label}>
            {label} · {chips.length} doc{chips.length === 1 ? "" : "s"}
          </span>
          {chips.slice(0, MAX_CHIPS).map((chip) => (
            <DocChip key={chip.key} chip={chip} />
          ))}
          {hidden > 0 && <span className="chip more">+{hidden}</span>}
        </>
      }
    >
      <ol className="citations">
        {items.map((c, i) => (
          <CitationCard key={`${c.source}:${c.path}:${i}`} c={c} />
        ))}
      </ol>
      {children}
    </CompactCard>
  );
}

const count = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

// whoami: "Signed in as Paul · 2 teams · 4 roles" in the line; the tags in the body.
function IdentityCard({ result }: { result: unknown }) {
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
  const facts = [
    me.teams.length > 0 && count(me.teams.length, "team"),
    me.roles.length > 0 && count(me.roles.length, "role"),
    me.groups.length > 0 && count(me.groups.length, "group"),
  ].filter(Boolean);
  return (
    <CompactCard
      line={
        <span className="tool-label">
          Signed in as <strong>{me.name ?? me.upn ?? "you"}</strong>
          {facts.length > 0 && ` · ${facts.join(" · ")}`}
        </span>
      }
    >
      {row("Teams", me.teams)}
      {row("Roles", me.roles)}
      {row("Groups", me.groups)}
      {row("App roles", me.appRoles)}
    </CompactCard>
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
      {typeof payload.connection_warning === "string" && (
        <div className="conn-state warn">
          {payload.connection_warning} <a href="/chat/connections">Connections</a>
        </div>
      )}
    </div>
  );
}

// Documents the agent saved for the user (version-03 P5). Links point only at /artifacts/<uuid>.
function ArtifactsResult({ result, label, saved }: { result: unknown; label: string; saved?: boolean }) {
  const items = savedArtifacts(result);
  const first = items[0]?.id;
  useEffect(() => {
    if (saved && first) window.dispatchEvent(new Event(ARTIFACTS_CHANGED)); // the panel refreshes
  }, [saved, first]);
  if (items.length === 0) return <div className="tool">{label}: none</div>;
  return (
    <div className="tool">
      <div className="tool-title">{label}</div>
      {items.map((a) => (
        <div key={a.id}>
          <a href={a.href} download={a.name}>
            {a.name}
          </a>{" "}
          <button type="button" className="link-button" onClick={() => openArtifact(a)}>
            Review
          </button>
          <div className="citation-meta">
            <span>{a.sizeBytes < 1024 ? `${a.sizeBytes} B` : `${Math.ceil(a.sizeBytes / 1024)} KB`}</span>
            {a.expiresAt && <span>kept until {a.expiresAt.slice(0, 10)}</span>}
            <span>only you can open it</span>
          </div>
        </div>
      ))}
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
        <Citations result={result} label={`Graph query “${args.query ?? ""}”`}>
          {entities.length > 0 && (
            <div className="entities">
              {entities.map((e) => (
                <span key={`${e.source}:${e.name}`} className="entity" title={`${e.type} · ${e.source}`}>
                  {e.name}
                </span>
              ))}
            </div>
          )}
        </Citations>
      );
    },
  }),
  defineToolCallRenderer({
    name: "whoami",
    args: whoamiArgs,
    render: ({ status, result }) =>
      done(status) ? <IdentityCard result={result} /> : <Pending label="Checking who you are" />,
  }),
  defineToolCallRenderer({
    name: "save_artifact",
    args: z.object({ name: z.string().optional() }).passthrough(),
    render: ({ status, result }) =>
      done(status) ? <ArtifactsResult result={result} label="Saved document" saved /> : <Pending label="Saving document" />,
  }),
  defineToolCallRenderer({
    name: "list_artifacts",
    args: z.object({}).passthrough(),
    render: ({ status, result }) =>
      done(status) ? <ArtifactsResult result={result} label="Your saved documents" /> : <Pending label="Listing documents" />,
  }),
];
