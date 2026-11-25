// Where sdlc_ui's backends are and how it proves itself to them. No React: unit-tested in tests/backends.test.ts.
//
// - SDLC_AGENT_URL: the user agent's Agent Runtime resource URL
//   (https://<region>-aiplatform.googleapis.com/v1/projects/<p>/locations/<region>/reasoningEngines/<id>), or
//   the local runtime server (http://user-agent:8085/v1/local). SDLC_AGENT_AUTH: `google` (an access token of
//   this service's account) or `none` (local only).
// - SDLC_MCP_URL: user_agent_mcp's URL. SDLC_MCP_AUTH: `id_token` (this service's ID token, audience the URL)
//   or `none` (local only: user_agent_mcp in identity mode trusted_header).

export type BackendSettings = {
  agentUrl: string;
  agentAuth: "google" | "none";
  mcpUrl: string;
  mcpAuth: "id_token" | "none";
};

const LOCAL = "local";

export function backendSettings(env: Record<string, string | undefined> = process.env): BackendSettings {
  const local = (env.SDLC_ENV ?? "") === LOCAL;
  const agentAuth = env.SDLC_AGENT_AUTH ?? "google";
  const mcpAuth = env.SDLC_MCP_AUTH ?? "id_token";
  if (agentAuth !== "google" && agentAuth !== "none") throw new Error("SDLC_AGENT_AUTH must be google or none");
  if (mcpAuth !== "id_token" && mcpAuth !== "none") throw new Error("SDLC_MCP_AUTH must be id_token or none");
  if ((agentAuth === "none" || mcpAuth === "none") && !local) {
    throw new Error("calling a backend without credentials is allowed only with SDLC_ENV=local");
  }
  const agentUrl = (env.SDLC_AGENT_URL ?? "").replace(/\/+$/, "");
  const mcpUrl = (env.SDLC_MCP_URL ?? "").replace(/\/+$/, "");
  if (!/^https?:\/\//.test(agentUrl) || !/^https?:\/\//.test(mcpUrl)) {
    throw new Error("SDLC_AGENT_URL and SDLC_MCP_URL must be set");
  }
  return { agentUrl, agentAuth, mcpUrl, mcpAuth };
}
