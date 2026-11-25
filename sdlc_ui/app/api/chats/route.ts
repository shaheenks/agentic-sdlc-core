import { chatSummaries } from "@/lib/events";
import { backends, json, withUser } from "@/lib/server";

export const dynamic = "force-dynamic";

// The user's own chats (FR-WFL-009), and a new one: a runtime session created for the verified user.
export const GET = (request: Request) =>
  withUser(request, async (user) => json({ chats: chatSummaries(await backends().agent.listSessions(user)) }));

const TEAM = /^[a-z][a-z0-9_-]{0,63}$/;

// A team chat (`{"team": "payments"}`) starts in that team's scope (FR-KNOW-004); the team must be one of the
// user's, as user_agent_mcp knows them. user_agent_mcp refuses a team the user is not in on every call anyway.
export const POST = (request: Request) =>
  withUser(request, async (user) => {
    const body = (await request.json().catch(() => ({}))) as { team?: unknown };
    const team = body?.team;
    if (team !== undefined) {
      if (typeof team !== "string" || !TEAM.test(team)) return json({ error: "invalid", message: "Not a team." }, 400);
      const me = await backends().mcp.call(user, "GET", "/api/me");
      const teams = (me.body as { teams?: Record<string, unknown> } | null)?.teams ?? {};
      if (me.status !== 200 || !(team in teams)) return json({ error: "forbidden", message: "You are not in that team." }, 403);
    }
    const session = (await backends().agent.createSession(user, team as string | undefined)) as { id?: unknown };
    if (typeof session?.id !== "string") return json({ error: "unavailable", message: "Could not start a chat." }, 502);
    return json({ id: session.id }, 201);
  });
