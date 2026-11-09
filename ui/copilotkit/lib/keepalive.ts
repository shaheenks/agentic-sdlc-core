// SSE keep-alive for the chat runtime's streamed responses (version-03 P10 fix, 2026-11-07).
// A long tool (a Goldfish review) sends no events for minutes; the Cloudflare tunnel and other
// proxies drop silent responses. While a text/event-stream response is idle, send an SSE comment
// line, which SSE clients ignore (the AG-UI client parses only `data:` lines).

export const KEEPALIVE = ": keep-alive\n\n";
export const KEEPALIVE_MS = 15_000;

export function withKeepAlive(response: Response, intervalMs = KEEPALIVE_MS): Response {
  const type = response.headers.get("content-type") ?? "";
  if (!response.body || !type.toLowerCase().startsWith("text/event-stream")) return response;
  const reader = response.body.getReader();
  const ping = new TextEncoder().encode(KEEPALIVE);
  let timer: ReturnType<typeof setInterval> | undefined;
  let last = Date.now();
  const stop = () => {
    if (timer) clearInterval(timer);
    timer = undefined;
  };
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      timer = setInterval(() => {
        if (Date.now() - last < intervalMs) return;
        try {
          controller.enqueue(ping);
          last = Date.now();
        } catch {
          stop(); // stream already closed
        }
      }, Math.max(50, Math.floor(intervalMs / 3)));
    },
    async pull(controller) {
      try {
        const { done, value } = await reader.read();
        if (done) {
          stop();
          controller.close();
          return;
        }
        last = Date.now();
        controller.enqueue(value);
      } catch (error) {
        stop();
        controller.error(error);
      }
    },
    cancel(reason) {
      stop();
      return reader.cancel(reason);
    },
  });
  return new Response(body, { status: response.status, statusText: response.statusText, headers: response.headers });
}
