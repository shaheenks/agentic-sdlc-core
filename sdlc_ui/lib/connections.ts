// What each connection provider needs, and how a sign-in check reads (FR-CONN-001). No React: unit-tested in
// tests/connections.test.ts.

export type Provider = { name: string; system?: string; edition: string };
export type Check = { status?: string; account?: string | null; reason?: string };

export type Fields = {
  account: { label: string; required: boolean; hint: string } | null;
  baseUrl: { label: string; hint: string } | null;
  token: string;
};

/** The form for one provider: what it signs in with. */
export function fieldsFor(provider: Provider | undefined): Fields {
  const system = provider?.system ?? "";
  const dataCenter = provider?.edition === "data_center";
  const baseUrl = dataCenter
    ? { label: "Server URL", hint: "Your server's https:// address, such as https://jira.example.com." }
    : null;
  if (system === "jira" || system === "confluence") {
    return dataCenter
      ? { account: null, baseUrl, token: "Personal access token" }
      : {
          account: { label: "Atlassian account email", required: true, hint: "The email you sign in to Atlassian with." },
          baseUrl: null,
          token: "API token (id.atlassian.com → Security → API tokens)",
        };
  }
  if (system === "bitbucket" && !dataCenter) {
    return {
      account: {
        label: "Username (only for an app password)",
        required: false,
        hint: "Leave empty for an access token; give your Bitbucket username for an app password.",
      },
      baseUrl: null,
      token: "Access token or app password",
    };
  }
  return { account: null, baseUrl, token: system === "github" ? "Personal access token (fine-grained or classic)" : "Personal access token" };
}

const REASONS: Record<string, string> = {
  unauthorized: "the token was not accepted",
  forbidden: "the token lacks the rights to sign in",
  invalid: "the sign-in details are incomplete",
};

/** One line for the result of a sign-in check. */
export function describeCheck(check: Check): string {
  if (check.status === "ok") return check.account ? `Signed in as ${check.account}` : "Signed in";
  if (check.status === "refused") return `Refused: ${REASONS[check.reason ?? ""] ?? check.reason ?? "unknown reason"}`;
  if (check.status === "untested") return `Not checked: ${check.reason ?? "nothing to test against"}`;
  return "Unknown";
}
