import type { NextConfig } from "next";

// The browser may only talk to this origin (the runtime is same-origin, behind oauth2-proxy):
// no third-party scripts, styles, fonts or network calls (e.g. vendor telemetry).
const csp = [
  "default-src 'self'",
  "connect-src 'self'",
  "script-src 'self' 'unsafe-inline'", // Next.js inline bootstrap scripts
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self' data:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

// Served behind oauth2-proxy at /chat (the proxy routes /chat/ here, everything else to the agent).
const config: NextConfig = {
  basePath: "/chat",
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ];
  },
};

export default config;
