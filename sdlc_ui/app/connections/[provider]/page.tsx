"use client";

import { useParams } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { api } from "@/lib/client";
import { type Check, describeCheck, fieldsFor, type Provider } from "@/lib/connections";

// The secure entry page (FR-CONN-005): the token goes from this form to the BFF and user_agent_mcp only, never
// into a chat. connection_start links here. user_agent_mcp signs in with the token before storing it: a token
// the provider refuses is not saved.
export default function ConnectProvider() {
  const { provider } = useParams<{ provider: string }>();
  const [info, setInfo] = useState<Provider | undefined>();
  const [secret, setSecret] = useState("");
  const [account, setAccount] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const [result, setResult] = useState<Check | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ providers: Record<string, Provider> }>("/api/connections").then(
      (listing) => setInfo(listing.providers[provider]),
      () => setInfo(undefined),
    );
  }, [provider]);
  const fields = fieldsFor(info);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setState("saving");
    setError("");
    try {
      const saved = await api<Check>(`/api/connections/${encodeURIComponent(provider)}`, {
        method: "PUT",
        body: JSON.stringify({ secret, ...(account ? { account } : {}), ...(baseUrl ? { base_url: baseUrl } : {}) }),
      });
      setSecret("");
      setResult(saved);
      setState("saved");
    } catch (e) {
      setSecret("");
      setError((e as Error).message);
      setState("idle");
    }
  };

  return (
    <main className="page narrow">
      <h1>Connect {info?.name ?? provider}</h1>
      {state === "saved" ? (
        <>
          <p className={`check-${result?.status ?? ""}`} role="status">
            Saved. {result ? describeCheck(result) : ""}
          </p>
          <p>
            <a href="/connections">Back to connections</a>
          </p>
        </>
      ) : (
        <form onSubmit={save}>
          {fields.baseUrl && (
            <label>
              {fields.baseUrl.label}
              <input type="url" required placeholder="https://" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
              <small className="hint">{fields.baseUrl.hint}</small>
            </label>
          )}
          {fields.account && (
            <label>
              {fields.account.label}
              <input
                required={fields.account.required}
                autoComplete="username"
                value={account}
                onChange={(e) => setAccount(e.target.value)}
              />
              <small className="hint">{fields.account.hint}</small>
            </label>
          )}
          <label>
            {fields.token}
            <input type="password" autoComplete="off" required value={secret} onChange={(e) => setSecret(e.target.value)} />
          </label>
          {error && <p className="error">{error}</p>}
          <button type="submit" className="primary" disabled={state === "saving" || !secret}>
            {state === "saving" ? "Checking and saving…" : "Check and save"}
          </button>
        </form>
      )}
    </main>
  );
}
