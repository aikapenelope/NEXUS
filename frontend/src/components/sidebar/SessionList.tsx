"use client";

import { useEffect, useState } from "react";

interface SessionInfo {
  session_id: string;
  agent: string;
  messages: number;
  created_at: number;
  last_active: number;
}

const API_URL =
  typeof window !== "undefined"
    ? `http://${window.location.hostname}:8000`
    : "http://localhost:8000";

export function SessionList() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API_URL}/sessions`);
        const data = await res.json();
        setSessions(data.sessions ?? []);
      } catch {
        // API not reachable
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  if (sessions.length === 0) {
    return (
      <div className="p-3">
        <p className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">
          Sessions
        </p>
        <p className="text-xs text-zinc-600">No active sessions</p>
      </div>
    );
  }

  return (
    <div className="p-3">
      <p className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">
        Sessions ({sessions.length})
      </p>
      <div className="space-y-1">
        {sessions.map((s) => (
          <div
            key={s.session_id}
            className="px-2 py-1.5 rounded text-xs bg-zinc-900 border border-zinc-800"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-zinc-400 text-[10px]">
                {s.session_id.slice(0, 12)}
              </span>
              <span className="text-[9px] text-zinc-600">
                {s.messages} msgs
              </span>
            </div>
            <div className="text-[10px] text-zinc-500 mt-0.5">{s.agent}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
