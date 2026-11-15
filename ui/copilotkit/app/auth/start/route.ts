// GET /chat/auth/start: server-side Google sign-in for the IAP user (native stack, CH-0016).
import { startSignIn } from "@/lib/auth-routes";
import { nativeEnabled } from "@/lib/native";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request): Promise<Response> {
  if (!nativeEnabled()) return new Response(null, { status: 404 });
  return startSignIn(request);
}
