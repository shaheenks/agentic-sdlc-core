import "./globals.css";

import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Header } from "@/components/Header";

export const metadata: Metadata = {
  title: "Agentic SDLC",
  description: "Chat with the platform's agents over the knowledge you may read",
};

// CopilotKit's dark theme follows a `dark` class; our colours follow the OS. Keep both in step.
const THEME_SCRIPT = `(function(){var m=window.matchMedia("(prefers-color-scheme: dark)");function s(){document.documentElement.classList.toggle("dark",m.matches)}s();m.addEventListener("change",s)})();`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* a fixed string, no user data */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>
        <Header />
        {children}
      </body>
    </html>
  );
}
