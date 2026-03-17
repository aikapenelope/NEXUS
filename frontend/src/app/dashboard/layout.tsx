"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bot,
  List,
  ArrowLeft,
  GitBranch,
  Wrench,
  Activity,
  FlaskConical,
} from "lucide-react";

const navItems = [
  { href: "/dashboard", icon: BarChart3, label: "Overview" },
  { href: "/dashboard/traces", icon: List, label: "Traces" },
  { href: "/dashboard/agents", icon: Bot, label: "Agents" },
  { href: "/dashboard/evals", icon: FlaskConical, label: "Evals" },
  { href: "/dashboard/workflows", icon: GitBranch, label: "Workflows" },
  { href: "/dashboard/tools", icon: Wrench, label: "Tools" },
  { href: "/dashboard/monitor", icon: Activity, label: "Monitor" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen bg-zinc-950">
      {/* Dashboard sidebar */}
      <aside className="w-56 border-r border-zinc-800 bg-zinc-950 flex flex-col">
        <div className="p-4 border-b border-zinc-800">
          <Link
            href="/"
            className="flex items-center gap-2 text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Chat
          </Link>
          <h1 className="text-lg font-semibold text-zinc-100 mt-3">Dashboard</h1>
          <p className="text-xs text-zinc-500 mt-0.5">NEXUS Observability</p>
        </div>
        <nav className="flex-1 p-2 space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-zinc-800 text-zinc-100"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-4 border-t border-zinc-800">
          <div className="text-xs text-zinc-600">NEXUS v0.4.0</div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto p-6">{children}</div>
      </main>
    </div>
  );
}
