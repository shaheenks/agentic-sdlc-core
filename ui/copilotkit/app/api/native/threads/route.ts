// GET /threads on the native stack: the caller's conversations from Agent Runtime (CH-0016).
import { threads } from "@/lib/native-api";
import { nativeEnabled } from "@/lib/native";
import { engineClient } from "@/lib/runtime";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request): Promise<Response> {
  if (!nativeEnabled()) return new Response(null, { status: 404 });
  return threads(request, engineClient());
}
