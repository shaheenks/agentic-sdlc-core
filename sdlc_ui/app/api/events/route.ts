import { backends, json, withUser } from "@/lib/server";

export const dynamic = "force-dynamic";

// Simulated events (FR-TRIG-006, DEC-0016): what the user may send, and sending one. The event gateway decides who
// may simulate and reads the pull request's facts itself; this route only forwards the verified user.
export const GET = (request: Request) =>
  withUser(request, async (user) => {
    const events = backends().events;
    if (!events.configured) return json({ enabled: false, teams: [] });
    const { status, body } = await events.simulate(user, "GET");
    return status === 200 ? json(body) : json({ enabled: false, teams: [] });
  });

export const POST = (request: Request) =>
  withUser(request, async (user) => {
    const events = backends().events;
    if (!events.configured) return json({ error: "not_found", message: "Simulated events are off here." }, 404);
    let form: unknown;
    try {
      form = await request.json();
    } catch {
      return json({ error: "bad_request", message: "Send a JSON object." }, 400);
    }
    const { status, body } = await events.simulate(user, "POST", form);
    return json(body, status);
  });
