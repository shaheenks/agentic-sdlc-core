import { backends, json, withUser } from "@/lib/server";

export const dynamic = "force-dynamic";

// Who the user is and what they may use, as user_agent_mcp sees them.
export const GET = (request: Request) =>
  withUser(request, async (user) => {
    const { status, body } = await backends().mcp.call(user, "GET", "/api/me");
    return json(body, status);
  });
