import { backends, json, withUser } from "@/lib/server";

export const dynamic = "force-dynamic";

const PROVIDER = /^[a-z][a-z0-9_-]{0,63}$/;
type Context = { params: Promise<{ provider: string }> };

// Test a saved connection (FR-CONN-001): user_agent_mcp signs in to the provider with the user's stored token and
// says as whom, or why not. The token never leaves user_agent_mcp.
export const POST = (request: Request, { params }: Context) =>
  withUser(request, async (user) => {
    const { provider } = await params;
    if (!PROVIDER.test(provider)) return json({ error: "not_found", message: "No such provider." }, 404);
    if (request.headers.get("x-sdlc-request") !== "1") return json({ error: "forbidden", message: "Not allowed." }, 403);
    const { status, body } = await backends().mcp.call(user, "POST", `/api/connections/${provider}/test`);
    return json(body, status);
  });
