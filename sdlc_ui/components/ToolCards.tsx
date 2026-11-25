"use client";

// Every tool call as a concise card (FR-AGT-005): what was done and what came of it in one line; what there is to
// inspect (search hits, issues, files, a workflow's outcome) in a collapsed body. A running workflow shows its
// current stage, which the BFF sends as the agent's state. Workflow questions have their own cards
// (WorkflowQuestions), which take precedence over this catch-all.

import { useAgent, UseAgentUpdate, useRenderTool } from "@copilotkit/react-core/v2";

import { type Card, toolCard } from "@/lib/toolcards";

const MARK: Record<Card["status"], string> = { running: "…", done: "✓", failed: "✕", stopped: "■" };

function Stage() {
  const { agent } = useAgent({ updates: [UseAgentUpdate.OnStateChanged] });
  const stage = (agent?.state as { progress?: unknown } | undefined)?.progress;
  return typeof stage === "string" && stage ? <span className="tool-stage">{stage}</span> : null;
}

function Items({ card }: { card: Card }) {
  if (!card.items?.length) return null;
  return (
    <ol className="tool-items">
      {card.items.map((item, i) => (
        <li key={`${item.title}-${i}`}>
          {item.link ? (
            <a href={item.link} target="_blank" rel="noreferrer noopener">
              {item.title}
            </a>
          ) : (
            <span className="tool-item-title">{item.title}</span>
          )}
          {item.meta && <small className="tool-meta"> · {item.meta}</small>}
          {item.text && <p>{item.text}</p>}
        </li>
      ))}
    </ol>
  );
}

function Facts({ card }: { card: Card }) {
  if (!card.facts?.length) return null;
  return (
    <dl className="tool-facts">
      {card.facts.map(([k, v], i) => (
        <div key={`${k}-${i}`}>
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
      {card.kind === "workflow" && card.status === "running" && <Stage />}
    </>
  );
  const hasBody = !!(card.items?.length || card.facts?.length || card.preview || card.link);
  if (!hasBody) return <div className={`tool-card tool-${card.kind}`}>{head}</div>;
  return (
    <details className={`tool-card tool-${card.kind}`} open={card.kind === "workflow" && card.status !== "running"}>
      <summary>{head}</summary>
      <div className="tool-body">
        <Facts card={card} />
        <Items card={card} />
        {card.preview && <pre className="tool-preview">{card.preview}</pre>}
        {card.link && (
          <a className="tool-link" href={card.link.href} target={card.link.href.startsWith("/") ? undefined : "_blank"} rel="noreferrer noopener">
            {card.link.label}
          </a>
        )}
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
