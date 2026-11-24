import type { ReactNode } from "react";

export const metadata = {
  title: "Agentic SDLC",
  description: "Run pre-defined agentic SDLC workflows.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
