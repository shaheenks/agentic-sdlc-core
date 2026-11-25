import { chatSummaries } from "@/lib/events";
import { backends, json, withUser } from "@/lib/server";

export const dynamic = "force-dynamic";

// The user's own chats (FR-WFL-009), and a new one: a runtime session created for the verified user.
export const GET = (request: Request) =>
  withUser(request, async (user) => json({ chats: chatSummaries(await backends().agent.listSessions(user)) }));

export const POST = (request: Request) =>
  withUser(request, async (user) => {
    const session = (await backends().agent.createSession(user)) as { id?: unknown };
    if (typeof session?.id !== "string") return json({ error: "unavailable", message: "Could not start a chat." }, 502);
    return json({ id: session.id }, 201);
  });
