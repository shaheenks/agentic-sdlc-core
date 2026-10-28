import { BASE_PATH, copilotHandler, RUNTIME_PATH } from "@/lib/runtime";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Next.js hands route handlers the URL without its basePath (/chat); the CopilotKit handler
// routes on the full public path, so put the basePath back before handing the request over.
function withBasePath(request: Request): Request {
  const url = new URL(request.url);
  if (url.pathname.startsWith(RUNTIME_PATH)) return request;
  url.pathname = BASE_PATH + url.pathname;
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  return new Request(url, {
    method: request.method,
    headers: request.headers,
    body: hasBody ? request.body : undefined,
    signal: request.signal,
    ...(hasBody ? { duplex: "half" } : {}),
  } as RequestInit);
}

const handle = (request: Request) => copilotHandler()(withBasePath(request));

export const GET = handle;
export const POST = handle;
export const PATCH = handle;
export const DELETE = handle;
