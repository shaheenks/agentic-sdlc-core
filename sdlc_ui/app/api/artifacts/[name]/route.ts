import { backends, json, withUser } from "@/lib/server";

export const dynamic = "force-dynamic";

const NAME = /^[A-Za-z0-9._-]{1,128}$/;
type Context = { params: Promise<{ name: string }> };

function artifactRoute(method: "GET" | "DELETE") {
  return (request: Request, { params }: Context) =>
    withUser(request, async (user) => {
      const { name } = await params;
      if (!NAME.test(name)) return json({ error: "not_found", message: "No such artifact." }, 404);
      const { status, body } = await backends().mcp.call(user, method, `/api/artifacts/${encodeURIComponent(name)}`);
      return status === 204 ? new Response(null, { status }) : json(body, status);
    });
}

export const GET = artifactRoute("GET");
export const DELETE = artifactRoute("DELETE");
