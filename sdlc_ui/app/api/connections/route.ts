import { backends, json, withUser } from "@/lib/server";

export const dynamic = "force-dynamic";

export const GET = (request: Request) =>
  withUser(request, async (user) => {
    const { status, body } = await backends().mcp.call(user, "GET", "/api/connections");
    return json(body, status);
  });
