"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/client";

type Subscription = {
  id: string;
  agent?: string;
  workflow?: string;
  description?: string;
  event: { provider?: string; type?: string; action?: string };
  subject: "pull_request" | "metadata";
  repositories: string[];
};
type Options = { enabled: boolean; teams: { team: string; subscriptions: Subscription[] }[] };
type Sent = { matched?: number; duplicate?: boolean; delivery_id?: string };

// Simulated events for the event agents until the webhooks are set up (FR-TRIG-006, DEC-0016). The event gateway
// reads the pull request from the provider; the run checks every approval on the systems themselves.
export default function EventsPage() {
  const [options, setOptions] = useState<Options | null>(null);
  const [team, setTeam] = useState("");
  const [subId, setSubId] = useState("");
  const [repository, setRepository] = useState("");
  const [number, setNumber] = useState("");
  const [subject, setSubject] = useState("");
  const [state, setState] = useState<"idle" | "sending">("idle");
  const [result, setResult] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<Options>("/api/events").then(
      (o) => {
        setOptions(o);
        if (o.teams.length) setTeam(o.teams[0].team);
      },
      (e: Error) => setError(e.message),
    );
  }, []);

  const subs = useMemo(() => options?.teams.find((t) => t.team === team)?.subscriptions ?? [], [options, team]);
  const sub = subs.find((s) => s.id === subId) ?? subs[0];
  useEffect(() => {
    setSubId(subs[0]?.id ?? "");
  }, [subs]);
  useEffect(() => {
    setRepository(sub?.repositories[0] ?? "");
  }, [sub]);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sub) return;
    setState("sending");
    setResult("");
    setError("");
    const form: Record<string, unknown> = { team, subscription: sub.id, repository };
    if (sub.subject === "pull_request") form.number = Number(number);
    else form.subject = subject;
    try {
      const sent = await api<Sent>("/api/events", { method: "POST", body: JSON.stringify(form) });
      setResult(
        sent.duplicate
          ? `Already sent (${sent.delivery_id}): no second run was started.`
          : `Sent as ${sent.delivery_id}: ${sent.matched} run${sent.matched === 1 ? "" : "s"} queued for ${sub.agent}.`,
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setState("idle");
    }
  };

  if (options === null) return <main className="page narrow">{error ? <p className="error">{error}</p> : <p>Loading…</p>}</main>;
  if (!options.enabled) {
    return (
      <main className="page narrow">
        <h1>Events</h1>
        <p className="empty">Simulated events are off here, or none of your teams may send them.</p>
      </main>
    );
  }
  return (
    <main className="page narrow">
      <h1>Events</h1>
      <p className="hint">
        Send an event to the event agents as if its webhook had arrived. The gateway reads the pull request from the
        provider, so only what really happened counts, and the same event starts one run.
      </p>
      <form onSubmit={send}>
        <label>
          Team
          <select value={team} onChange={(e) => setTeam(e.target.value)}>
            {options.teams.map((t) => (
              <option key={t.team} value={t.team}>
                {t.team}
              </option>
            ))}
          </select>
        </label>
        <label>
          Subscription
          <select value={sub?.id ?? ""} onChange={(e) => setSubId(e.target.value)}>
            {subs.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id} ({s.agent}: {s.workflow})
              </option>
            ))}
          </select>
          {sub && (
            <small className="hint">
              {sub.event.provider} {sub.event.type}
              {sub.event.action ? `.${sub.event.action}` : ""}. {sub.description}
            </small>
          )}
        </label>
        {sub && sub.repositories.length > 0 && (
          <label>
            Repository
            <select value={repository} onChange={(e) => setRepository(e.target.value)}>
              {sub.repositories.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
        )}
        {sub?.subject === "pull_request" ? (
          <label>
            Pull request number
            <input type="number" min={1} required value={number} onChange={(e) => setNumber(e.target.value)} />
          </label>
        ) : (
          <label>
            Subject
            <input type="text" required value={subject} onChange={(e) => setSubject(e.target.value)} />
          </label>
        )}
        {error && <p className="error">{error}</p>}
        {result && <p role="status">{result}</p>}
        <button type="submit" className="primary" disabled={state === "sending" || !sub}>
          {state === "sending" ? "Sending…" : "Send event"}
        </button>
      </form>
    </main>
  );
}
