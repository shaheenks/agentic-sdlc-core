import { withKeepAlive } from "@/lib/keepalive";
import { asUser, backends, withUser } from "@/lib/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// The chat stream: the verified user replaces any user headers the browser sent, then CopilotKit's runtime
// relays the agent's answer as AG-UI, with keep-alive comments while a long tool runs.
const handle = (request: Request) =>
  withUser(request, async (user) => withKeepAlive(await backends().copilot(asUser(request, user))));

export const GET = handle;
export const POST = handle;
export const PATCH = handle;
export const DELETE = handle;
