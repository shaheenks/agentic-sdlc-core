"use client";

import { useParams } from "next/navigation";
import { type FormEvent, useState } from "react";

import { api } from "@/lib/client";

// The secure entry page (FR-CONN-005): the token goes from this form to the BFF and user_agent_mcp only, never
// into a chat. connection_start links here.
export default function ConnectProvider() {
  const { provider } = useParams<{ provider: string }>();
  const [secret, setSecret] = useState("");
  const [account, setAccount] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const [error, setError] = useState("");

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setState("saving");
    setError("");
    try {
      await api(`/api/connections/${encodeURIComponent(provider)}`, {
        method: "PUT",
        body: JSON.stringify({ secret, ...(account ? { account } : {}) }),
      });
      setSecret("");
      setState("saved");
    } catch (e) {
      setError((e as Error).message);
      setState("idle");
    }
  };

  return (
    <main className="page narrow">
      <h1>Connect {provider}</h1>
      {state === "saved" ? (
        <p>
          Saved. <a href="/connections">Back to connections</a>
        </p>
      ) : (
        <form onSubmit={save}>
          <label>
            Personal access token
            <input type="password" autoComplete="off" required value={secret} onChange={(e) => setSecret(e.target.value)} />
          </label>
          <label>
            Account (optional)
            <input value={account} onChange={(e) => setAccount(e.target.value)} />
          </label>
          {error && <p className="error">{error}</p>}
          <button type="submit" className="primary" disabled={state === "saving" || !secret}>
            {state === "saving" ? "Saving…" : "Save"}
          </button>
        </form>
      )}
    </main>
  );
}
