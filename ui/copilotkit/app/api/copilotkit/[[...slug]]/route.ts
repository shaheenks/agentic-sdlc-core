import { withKeepAlive } from "@/lib/keepalive";
import { nativeEnabled, refusal, resolveUser, withSession } from "@/lib/native";
import { BASE_PATH, copilotHandler, RUNTIME_PATH, TOKEN_HEADER } from "@/lib/runtime";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Next.js hands route handlers the URL without its basePath (/chat); the CopilotKit handler
// routes on the full public path, so put the basePath back before handing the request over.
function forRuntime(request: Request, headers: Headers = request.headers): Request {
  const url = new URL(request.url);
  if (!url.pathname.startsWith(RUNTIME_PATH)) url.pathname = BASE_PATH + url.pathname;
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  return new Request(url, {
    method: request.method,
    headers,
    body: hasBody ? request.body : undefined,
    signal: request.signal,
    ...(hasBody ? { duplex: "half" } : {}),
  } as RequestInit);
}

// streamed answers get keep-alive comments while a long tool runs (lib/keepalive.ts)
const handle = async (request: Request) => {
  if (!nativeEnabled()) return withKeepAlive(await copilotHandler()(forRuntime(request)));
  // native stack (CH-0016): IAP + session first; the verified ID token replaces whatever the
  // client sent in the token header, and is the only thing forwarded to the agent
  const resolved = await resolveUser(request);
  if (!resolved.ok) return refusal(resolved);
  const headers = new Headers(request.headers);
  headers.set(TOKEN_HEADER, resolved.idToken);
  return withSession(withKeepAlive(await copilotHandler()(forRuntime(request, headers))), resolved);
};

export const GET = handle;
export const POST = handle;
export const PATCH = handle;
export const DELETE = handle;
