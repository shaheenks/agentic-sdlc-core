// GET /me on the native stack (rewritten here by next.config.ts, CH-0016).
import { me } from "@/lib/native-api";
import { nativeEnabled } from "@/lib/native";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request): Promise<Response> {
  if (!nativeEnabled()) return new Response(null, { status: 404 });
  return me(request);
}
