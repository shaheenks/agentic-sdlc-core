import { BackendError } from "@/lib/backends";
import { CHAT_ID } from "@/lib/events";
import { backends, json, withUser } from "@/lib/server";

export const dynamic = "force-dynamic";

type Context = { params: Promise<{ id: string }> };

export const DELETE = (request: Request, { params }: Context) =>
  withUser(request, async (user) => {
    const { id } = await params;
    if (!CHAT_ID.test(id)) return json({ error: "not_found", message: "No such chat." }, 404);
    try {
      await backends().agent.deleteSession(user, id);
    } catch (error) {
      if (error instanceof BackendError && error.status < 500) return json({ error: "not_found", message: "No such chat." }, 404);
      throw error;
    }
    return new Response(null, { status: 204 });
  });
