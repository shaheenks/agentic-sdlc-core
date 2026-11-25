// How long the agent took (FR-AGT-005), measured in the browser while the chat is open: each assistant message
// shows when it arrived after the user's message, and the turn's last one the turn's total once it has ended.
// Messages already there when the chat opened (its history) are not timed. No React: tests/timing.test.ts.

export type Turn = { start: number; end?: number };

export class RunClock {
  private readonly firstSeen = new Map<string, number>();
  private readonly turns: Turn[] = [];
  private running = false;

  /** Call on every render with the current messages and whether the agent is running. */
  observe(messageIds: string[], isRunning: boolean, now: number): void {
    if (isRunning && !this.running) this.turns.push({ start: now });
    if (!isRunning && this.running && this.turns.length) this.turns[this.turns.length - 1].end = now;
    this.running = isRunning;
    for (const id of messageIds) if (!this.firstSeen.has(id)) this.firstSeen.set(id, now);
  }

  /** The turn a message arrived in, or nothing for messages from before the first turn (history). */
  private turnOf(id: string): Turn | undefined {
    const seen = this.firstSeen.get(id);
    if (seen === undefined) return undefined;
    for (let i = this.turns.length - 1; i >= 0; i--) if (this.turns[i].start <= seen) return this.turns[i];
    return undefined;
  }

  /** "+2.4 s", and for the last message of an ended turn " · total 9.8 s". */
  label(id: string, isLastOfTurn: boolean): string {
    const turn = this.turnOf(id);
    const seen = this.firstSeen.get(id);
    if (!turn || seen === undefined) return "";
    const after = `+${seconds(seen - turn.start)}`;
    return isLastOfTurn && turn.end !== undefined ? `${after} · total ${seconds(turn.end - turn.start)}` : after;
  }
}

export function seconds(ms: number): string {
  const s = Math.max(0, ms) / 1000;
  if (s < 60) return `${s < 10 ? s.toFixed(1) : Math.round(s)} s`;
  return `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
}
