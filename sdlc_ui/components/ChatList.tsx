"use client";

import { type Chat, formatWhen } from "@/lib/client";

export function ChatList(props: {
  chats: Chat[];
  activeId: string | null;
  onSelect: (id: string) => void;
  teams: string[];
  onNew: (team?: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <aside className="chats">
      <button type="button" className="primary" onClick={() => props.onNew()}>
        New chat
      </button>
      {props.teams.length > 0 && (
        <div className="team-chats" aria-label="New chat for a team">
          <span>For a team:</span>
          {props.teams.map((team) => (
            <button type="button" key={team} onClick={() => props.onNew(team)} title={`A new chat in ${team}'s scope`}>
              {team}
            </button>
          ))}
        </div>
      )}
      <ul>
        {props.chats.map((c) => (
          <li key={c.id} className={c.id === props.activeId ? "active" : ""}>
            <button type="button" className="chat-title" onClick={() => props.onSelect(c.id)} title={c.title}>
              <span>{c.title}</span>
              {c.team && <em className="team">{c.team}</em>}
              <small>{formatWhen(c.updatedAt)}</small>
            </button>
            <button type="button" className="icon" aria-label={`Delete ${c.title}`} onClick={() => props.onDelete(c.id)}>
              ×
            </button>
          </li>
        ))}
        {!props.chats.length && <li className="empty">No chats yet.</li>}
      </ul>
    </aside>
  );
}
