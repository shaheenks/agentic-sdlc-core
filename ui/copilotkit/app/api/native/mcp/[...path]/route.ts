// /connections/* and /artifacts/* on the native stack, proxied to sdlc-mcp-native (CH-0016).
import { ServiceTokens } from "@/lib/gcp";
import { mcpSettings, proxyToMcp } from "@/lib/native-api";
import { nativeEnabled } from "@/lib/native";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

let tokens: ServiceTokens | undefined;

async function handle(request: Request, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  if (!nativeEnabled()) return new Response(null, { status: 404 });
  tokens ??= new ServiceTokens();
  return proxyToMcp(request, (await context.params).path, mcpSettings(), tokens);
}

export const GET = handle;
export const PUT = handle;
export const DELETE = handle;
