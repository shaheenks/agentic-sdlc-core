"use client";

// Every tool call as a concise card (FR-AGT-005): one line with what was done and how it went; knowledge queries
// keep their results in a collapsed section the user can open. Workflow questions have their own cards
// (WorkflowQuestions), which take precedence over this catch-all.

import { useRenderTool } from "@copilotkit/react-core/v2";

import { type Card, toolCard } from "@/lib/toolcards";

const MARK: Record<Card["status"], string> = { running: "…", done: "✓", failed: "✕", stopped: "■" };

function Hits({ card }: { card: Card }) {
  if (!card.hits?.length) return <p className="tool-empty">No results in the knowledge you may read.</p>;
  return (
    <ol className="tool-hits">
      {card.hits.map((h, i) => (
        <li key={`${h.path}-${i}`}>
          <div>
            {h.link ? (
              <a href={h.link} target="_blank" rel="noreferrer noopener">
                {h.path}
              </a>
            ) : (
              <code>{h.path}</code>
            )}
            {h.lines && <small> lines {h.lines}</small>}
            <small className="tool-meta">
              {" "}
              · {h.source}
              {h.score !== undefined ? ` · score ${h.score.toFixed(3)}` : ""}
            </small>
          </div>
          {h.heading && <div className="tool-heading">{h.heading}</div>}
          <p>{h.snippet}</p>
        </li>
      ))}
    </ol>
  );
}

function Graph({ card }: { card: Card }) {
  const g = card.graph;
  if (!g?.nodes.length) return <p className="tool-empty">Nothing found in the knowledge you may read.</p>;
  return (
    <ul className="tool-nodes">
      {g.nodes.slice(0, 40).map((n, i) => (
        <li key={`${n.name}-${i}`}>
          <strong>{n.name}</strong> <small className="tool-meta">{n.kind}</small>
          {n.path && <small className="tool-meta"> · {n.path}</small>}
        </li>
      ))}
      {g.nodes.length > 40 && <li className="tool-meta">and {g.nodes.length - 40} more</li>}
    </ul>
  );
}

function Facts({ card }: { card: Card }) {
  if (!card.facts?.length) return null;
  return (
    <dl className="tool-facts">
      {card.facts.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function ToolCard({ card }: { card: Card }) {
  const head = (
    <>
      <span className={`tool-mark tool-${card.status}`} aria-label={card.status}>
        {MARK[card.status]}
      </span>
      <span className="tool-label">{card.label}</span>
      {card.detail && <span className="tool-detail">{card.detail}</span>}
    </>
  );
  const expandable = card.kind === "knowledge" ? card.status !== "running" : !!card.facts?.length || !!card.error;
  if (!expandable) return <div className={`tool-card tool-${card.kind}`}>{head}</div>;
  return (
    <details className={`tool-card tool-${card.kind}`} open={card.kind === "workflow" && card.status !== "running"}>
      <summary>{head}</summary>
      <div className="tool-body">
        {card.error && <p className="error">{card.error}</p>}
        {card.hits && <Hits card={card} />}
        {card.graph && <Graph card={card} />}
        <Facts card={card} />
      </div>
    </details>
  );
}

export function ToolCards() {
  useRenderTool({
    name: "*",
    render: (props: { name: string; parameters: unknown; status: string; result?: string }) => (
      <ToolCard card={toolCard(props.name, props.parameters, props.status, props.result)} />
    ),
  });
  return null;
}
