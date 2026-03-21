"use client";

import { useNexusStore } from "@/stores/nexus";

export function TodoProgress() {
  const { todos } = useNexusStore();

  if (todos.length === 0) return null;

  const completed = todos.filter((t) => t.status === "completed").length;

  return (
    <div className="p-3">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] uppercase tracking-wider text-zinc-500">
          Todos
        </p>
        <span className="text-[10px] text-zinc-500">
          {completed}/{todos.length}
        </span>
      </div>
      <div className="space-y-1">
        {todos.map((todo, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span
              className={`w-3 h-3 rounded-full border flex-shrink-0 ${
                todo.status === "completed"
                  ? "bg-emerald-600 border-emerald-500"
                  : todo.status === "in_progress"
                    ? "bg-amber-600 border-amber-500 animate-pulse"
                    : "border-zinc-600"
              }`}
            />
            <span
              className={
                todo.status === "completed"
                  ? "text-zinc-500 line-through"
                  : "text-zinc-300"
              }
            >
              {todo.title}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
