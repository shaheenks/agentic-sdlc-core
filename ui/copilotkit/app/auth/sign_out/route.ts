// GET /chat/auth/sign_out (also /oauth2/sign_out, next.config.ts): ends the session (CH-0016).
import { signOut } from "@/lib/auth-routes";
import { nativeEnabled } from "@/lib/native";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(): Promise<Response> {
  if (!nativeEnabled()) return new Response(null, { status: 404 });
  return signOut();
}
