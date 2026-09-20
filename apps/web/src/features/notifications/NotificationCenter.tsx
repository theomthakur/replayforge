import { useState } from "react";

import type { Lane } from "../../api/types";
import type { Notification } from "../experiments/labState";

export function NotificationCenter({ notifications, onOpen }: { notifications: Notification[]; onOpen: (taskId: string, lane?: Lane) => void }) {
  const [open, setOpen] = useState(false);
  const urgent = notifications.filter((n) => n.severity === "error").length;
  return (
    <div className="notes">
      <button className="btn" aria-expanded={open} aria-controls="notification-panel" onClick={() => setOpen(!open)}>
        Notifications <span className={`badge ${urgent ? "failed" : ""}`}>{notifications.length}</span>
      </button>
      {open && (
        <div id="notification-panel" className="panel notes-panel" role="region" aria-label="Notifications">
          {notifications.length === 0 && <p className="body hint">No notifications yet.</p>}
          {notifications.map((n) => (
            <button key={n.id} className="note" onClick={() => { if (n.taskId) { onOpen(n.taskId, n.lane); setOpen(false); } }} disabled={!n.taskId}>
              <strong><span className={`badge ${n.severity}`}>{n.severity}</span> {n.title}</strong>
              <span>{n.detail}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function NotificationFeed({ notifications, onOpen }: { notifications: Notification[]; onOpen: (taskId: string, lane?: Lane) => void }) {
  if (notifications.length === 0) return null;
  return <section className="notification-feed" aria-label="Latest workflow notifications">
    <div><span className="eyebrow">Workflow notifications</span><small>Generated from persisted events</small></div>
    <ol>{notifications.slice(0, 3).map((note) => <li key={note.id} className={note.severity}>
      <i aria-hidden="true" />
      <button onClick={() => note.taskId && onOpen(note.taskId, note.lane)} disabled={!note.taskId}>
        <strong>{note.title}</strong><span>{note.detail}</span>
      </button>
      <b>{note.severity}</b>
    </li>)}</ol>
  </section>;
}
