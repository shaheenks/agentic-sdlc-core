import "./globals.css";

import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "SDLC assistant",
  description: "Chat with the SDLC agents over your team's knowledge",
};

// CopilotKit's dark theme follows a `dark` class, not the OS setting; our own colours follow the
// OS (globals.css). Keep both in step, before first paint and when the OS setting changes.
const THEME_SCRIPT = `(function(){var m=window.matchMedia("(prefers-color-scheme: dark)");function s(){document.documentElement.classList.toggle("dark",m.matches)}s();m.addEventListener("change",s)})();`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* fixed string, no user data; CSP allows inline scripts for Next's bootstrap */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
