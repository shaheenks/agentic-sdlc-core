"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/client";

type Me = { email?: string; teams?: Record<string, string[]> };

const LINKS = [
  { href: "/", label: "Chat" },
  { href: "/artifacts", label: "Artifacts" },
  { href: "/connections", label: "Connections" },
];
const EVENTS = { href: "/events", label: "Events" }; // only where the user may simulate events (DEC-0016)

// IAP's sign-out: clears its login cookie; the next request signs in again.
const SIGN_OUT = "/_gcp_iap/clear_login_cookie";

export function Header() {
  const path = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [events, setEvents] = useState(false);
  useEffect(() => {
    api<Me>("/api/me").then(setMe, () => setMe(null));
    api<{ enabled: boolean }>("/api/events").then((e) => setEvents(e.enabled), () => setEvents(false));
  }, []);
  const links = events ? [...LINKS, EVENTS] : LINKS;
  const teams = Object.keys(me?.teams ?? {});
  return (
    <header className="topbar">
      <a className="brand" href="/">Agentic SDLC</a>
      <nav>
        {links.map((l) => (
          <a key={l.href} href={l.href} className={(l.href === "/" ? path === "/" : path.startsWith(l.href)) ? "active" : ""}>
            {l.label}
          </a>
        ))}
      </nav>
      <div className="who">
        {me?.email && <span title={teams.length ? `Teams: ${teams.join(", ")}` : "No team"}>{me.email}</span>}
        <a href={SIGN_OUT}>Sign out</a>
      </div>
    </header>
  );
}
