import { health } from "../../../lib/health.ts";

export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json(health());
}
