// Entry point of the chat app on the native stack (CH-0016): `node native-entry.mjs`.
//
// Behind oauth2-proxy (local, Entra stack) the proxy routes /chat/ here and /me, /threads,
// /connections/, /artifacts/ elsewhere. On the native stack IAP is the only thing in front, so
// this small proxy maps those same-origin paths onto the app's own route handlers under
// /chat/api/native/* (Next.js cannot rewrite outside its basePath) and sends / to /chat/. It
// runs the Next.js standalone server on an internal port and passes every request and response
// through unchanged otherwise (headers, the IAP assertion, streamed bodies). No user data is
// read or logged here. Plain JavaScript: it runs in the runtime image without a build step.

import { spawn } from "node:child_process";
import http from "node:http";
import { fileURLToPath } from "node:url";

const ROUTES = [
  [/^\/me(\?.*)?$/, "/chat/api/native/me"],
  [/^\/threads(\/[^/?]*)?(\?.*)?$/, "/chat/api/native/threads"],
  [/^\/connections(\/.*)?$/, "/chat/api/native/mcp/connections"],
  [/^\/artifacts(\/.*)?$/, "/chat/api/native/mcp/artifacts"],
  [/^\/oauth2\/sign_out(\?.*)?$/, "/chat/auth/sign_out"],
];

/** The internal path for a public one; `null` for "/" (redirect to /chat/). */
export function mapPath(url) {
  if (url === "/" || url === "") return null;
  for (const [pattern, target] of ROUTES) {
    if (!pattern.test(url)) continue;
    // keep what follows the public prefix (sub-path and query): /threads/t1 -> .../threads/t1
    return target + url.replace(/^\/(me|threads|connections|artifacts|oauth2\/sign_out)/, "");
  }
  return url; // /chat/... and anything else: unchanged
}

function main() {
  const publicPort = Number(process.env.PORT || 3000);
  const nextPort = publicPort + 1;
  const here = fileURLToPath(new URL(".", import.meta.url));
  const next = spawn(process.execPath, ["server.js"], {
    cwd: here,
    env: { ...process.env, PORT: String(nextPort), HOSTNAME: "127.0.0.1" },
    stdio: "inherit",
  });
  next.on("exit", (code) => process.exit(code ?? 1));
  for (const signal of ["SIGTERM", "SIGINT"]) process.on(signal, () => next.kill(signal));

  http
    .createServer((req, res) => {
      const path = mapPath(req.url ?? "/");
      if (path === null) {
        res.writeHead(302, { location: "/chat/", "cache-control": "no-store" });
        res.end();
        return;
      }
      const upstream = http.request(
        { host: "127.0.0.1", port: nextPort, method: req.method, path, headers: req.headers },
        (answer) => {
          res.writeHead(answer.statusCode ?? 502, answer.headers);
          answer.pipe(res);
        },
      );
      upstream.on("error", () => {
        if (!res.headersSent) res.writeHead(502, { "content-type": "text/plain" });
        res.end("The chat app is starting. Please retry.");
      });
      req.pipe(upstream);
    })
    .listen(publicPort, process.env.HOSTNAME || "0.0.0.0");
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
