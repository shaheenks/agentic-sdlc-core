export const SERVICE = "sdlc_ui";

export type Health = { service: string; status: "ok" };

export function health(): Health {
  return { service: SERVICE, status: "ok" };
}
