// GET /chat/auth/callback: Google's redirect back; starts the session (native stack, CH-0016).
import { finishSignIn } from "@/lib/auth-routes";
import { nativeEnabled } from "@/lib/native";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request): Promise<Response> {
  if (!nativeEnabled()) return new Response(null, { status: 404 });
  return finishSignIn(request);
}
