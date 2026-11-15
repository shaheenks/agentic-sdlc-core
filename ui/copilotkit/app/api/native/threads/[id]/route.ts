// DELETE /threads/<id> on the native stack: deletes one of the caller's conversations (CH-0016).
import { threads } from "@/lib/native-api";
import { nativeEnabled } from "@/lib/native";
import { engineClient } from "@/lib/runtime";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function DELETE(request: Request, context: { params: Promise<{ id: string }> }): Promise<Response> {
  if (!nativeEnabled()) return new Response(null, { status: 404 });
  return threads(request, engineClient(), (await context.params).id);
}
