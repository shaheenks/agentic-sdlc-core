import { backends, json, withUser } from "@/lib/server";

export const dynamic = "force-dynamic";

const PROVIDER = /^[a-z][a-z0-9_-]{0,63}$/;
type Context = { params: Promise<{ provider: string }> };

// The secure entry page's save (FR-CONN-005): the secret goes from this form to user_agent_mcp only. It is
// never sent to the agent or logged. A cross-site page cannot send the custom header without a preflight.
export const PUT = (request: Request, { params }: Context) =>
  withUser(request, async (user) => {
    const { provider } = await params;
    if (!PROVIDER.test(provider)) return json({ error: "not_found", message: "No such provider." }, 404);
    if (request.headers.get("x-sdlc-request") !== "1") return json({ error: "forbidden", message: "Not allowed." }, 403);
    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return json({ error: "invalid_argument", message: "Expected JSON." }, 400);
    }
    const { status, body: answer } = await backends().mcp.call(user, "PUT", `/api/connections/${provider}`, body);
    return json(answer, status);
  });

export const DELETE = (request: Request, { params }: Context) =>
  withUser(request, async (user) => {
    const { provider } = await params;
    if (!PROVIDER.test(provider)) return json({ error: "not_found", message: "No such provider." }, 404);
    if (request.headers.get("x-sdlc-request") !== "1") return json({ error: "forbidden", message: "Not allowed." }, 403);
    const { status, body } = await backends().mcp.call(user, "DELETE", `/api/connections/${provider}`);
    return status === 204 ? new Response(null, { status }) : json(body, status);
  });
