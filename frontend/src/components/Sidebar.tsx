"use client";

import Link from "next/link";
import { Bot, Brain, Database, Wrench, MessageSquare, BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";

interface SidebarProps {
  activePanel: string;
  onPanelChange?: (panel: string) => void;
}

const navItems = [
  { id: "chat", icon: MessageSquare, label: "Chat" },
  { id: "agents", icon: Bot, label: "Agents" },
  { id: "cerebro", icon: Brain, label: "Cerebro" },
  { id: "memory", icon: Database, label: "Memory" },
  { id: "tools", icon: Wrench, label: "Tools" },
];

export function Sidebar({ activePanel, onPanelChange }: SidebarProps) {
  return (
    <aside className="w-16 flex flex-col items-center py-4 border-r border-zinc-800 bg-zinc-950">
      <div className="mb-6">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center">
          <Bot className="w-4 h-4 text-emerald-400" />
        </div>
      </div>
      <nav className="flex flex-col gap-2 flex-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              title={item.label}
              onClick={() => onPanelChange?.(item.id)}
              className={cn(
                "w-10 h-10 rounded-lg flex items-center justify-center transition-colors",
                activePanel === item.id
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
              )}
            >
              <Icon className="w-5 h-5" />
            </button>
          );
        })}
      </nav>

      {/* Dashboard link at bottom */}
      <div className="mt-auto pt-4 border-t border-zinc-800">
        <Link
          href="/dashboard"
          title="Dashboard"
          className="w-10 h-10 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 transition-colors"
        >
          <BarChart3 className="w-5 h-5" />
        </Link>
      </div>
    </aside>
  );
}
