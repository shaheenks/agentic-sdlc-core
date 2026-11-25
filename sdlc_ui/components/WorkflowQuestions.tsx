"use client";

// A workflow's questions in the chat (FR-HUM-001, FR-SDLC-004, DEC-0012): user_agent's workflows pause with
// `adk_request_input`; this renders each one and sends the user's answer back, which resumes the workflow.
// The answer is only ever text the user chose; what it means is decided by the workflow and user_agent_mcp.

import { useHumanInTheLoop } from "@copilotkit/react-core/v2";
import { useState } from "react";

type Finding = { id: string; reviewer: string; severity: string; location: string; problem: string; suggestion: string };
type Payload = {
  kind?: string;
  round?: number;
  findings?: Finding[];
  from?: string;
  to?: string;
  control_id?: string;
  pull_request?: { url?: string; number?: number };
};
type Args = { message?: string; payload?: Payload };
type Respond = ((answer: unknown) => Promise<void>) | undefined;

const safeLink = (url?: string) => (url && /^https:\/\//.test(url) ? url : undefined);

function Answered({ result }: { result?: string }) {
  let text = result ?? "";
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed === "string") text = parsed;
  } catch {
    /* plain text */
  }
  return <p className="answered">Answered: {text || "—"}</p>;
}

function Findings({ payload, respond }: { payload: Payload; respond: Respond }) {
  const findings = payload.findings ?? [];
  const [chosen, setChosen] = useState<Set<string>>(
    () => new Set(findings.filter((f) => f.severity === "blocker" || f.severity === "major").map((f) => f.id)),
  );
  const [note, setNote] = useState("");
  const toggle = (id: string) =>
    setChosen((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const apply = () => {
    const ids = findings.filter((f) => chosen.has(f.id)).map((f) => f.id);
    if (!ids.length && !note.trim()) return respond?.("stop");
    return respond?.([ids.join(", "), note.trim()].filter(Boolean).join(" — "));
  };
  return (
    <>
      <ul className="findings">
        {findings.map((f) => (
          <li key={f.id} className={`severity-${f.severity}`}>
            <label>
              <input type="checkbox" checked={chosen.has(f.id)} onChange={() => toggle(f.id)} disabled={!respond} />
              <span className="badge">{f.severity}</span> <strong>{f.id}</strong> {f.location} <small>({f.reviewer})</small>
            </label>
            <p>{f.problem}</p>
            <p className="suggestion">{f.suggestion}</p>
          </li>
        ))}
      </ul>
      <textarea
        placeholder="Changes of your own (optional)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        disabled={!respond}
        rows={2}
      />
      <div className="actions">
        <button type="button" className="primary" onClick={apply} disabled={!respond}>
          Apply selected
        </button>
        <button type="button" onClick={() => respond?.("stop")} disabled={!respond}>
          Keep it as it is
        </button>
      </div>
    </>
  );
}

function FreeText({ respond }: { respond: Respond }) {
  const [text, setText] = useState("");
  return (
    <div className="actions">
      <input value={text} onChange={(e) => setText(e.target.value)} disabled={!respond} placeholder="Your answer" />
      <button type="button" className="primary" onClick={() => text.trim() && respond?.(text.trim())} disabled={!respond}>
        Send
      </button>
    </div>
  );
}

function Question({ args, respond, result }: { args: Args; respond: Respond; result?: string }) {
  const payload = args.payload ?? {};
  const link = safeLink(payload.pull_request?.url);
  return (
    <div className="question" role="group" aria-label="The workflow asks">
      <p className="message">{args.message}</p>
      {result !== undefined ? (
        <Answered result={result} />
      ) : payload.kind === "review_findings" ? (
        <Findings payload={payload} respond={respond} />
      ) : payload.kind === "team_scope" ? (
        <div className="actions">
          <button type="button" className="primary" onClick={() => respond?.("yes")} disabled={!respond}>
            Switch to {payload.to}
          </button>
          <button type="button" onClick={() => respond?.("no")} disabled={!respond}>
            Stay in {payload.from}
          </button>
        </div>
      ) : payload.kind === "merge_wait" ? (
        <div className="actions">
          {link && (
            <a href={link} target="_blank" rel="noreferrer noopener">
              Open the pull request
            </a>
          )}
          <button type="button" className="primary" onClick={() => respond?.("merged")} disabled={!respond}>
            It is merged
          </button>
          <button type="button" onClick={() => respond?.("cancel")} disabled={!respond}>
            Cancel
          </button>
        </div>
      ) : (
        <FreeText respond={respond} />
      )}
    </div>
  );
}

export function WorkflowQuestions() {
  useHumanInTheLoop<Args>({
    name: "adk_request_input",
    description: "A question from a running workflow; the user answers it here.",
    render: (props) => (
      <Question
        args={(props.args ?? {}) as Args}
        respond={props.respond as Respond}
        result={props.status === "complete" ? (props.result as string) : undefined}
      />
    ),
  });
  return null;
}
