"use client";

interface DiffViewerProps {
  diff: string;
}

/**
 * Simple diff viewer with syntax highlighting for git diffs.
 * Shows added lines in green, removed in red, headers in blue.
 */
export function DiffViewer({ diff }: DiffViewerProps) {
  if (!diff) {
    return (
      <div className="p-3 text-xs text-zinc-600 text-center mt-4">
        No diff available
      </div>
    );
  }

  const lines = diff.split("\n");

  return (
    <div className="h-full overflow-y-auto bg-zinc-950 p-3 font-mono text-xs leading-relaxed">
      {lines.map((line, i) => {
        let className = "text-zinc-400";
        if (line.startsWith("+++") || line.startsWith("---")) {
          className = "text-blue-400 font-medium";
        } else if (line.startsWith("@@")) {
          className = "text-purple-400";
        } else if (line.startsWith("+")) {
          className = "text-emerald-400 bg-emerald-950/30";
        } else if (line.startsWith("-")) {
          className = "text-red-400 bg-red-950/30";
        } else if (line.startsWith("diff ")) {
          className = "text-zinc-300 font-medium border-t border-zinc-800 pt-2 mt-2";
        }

        return (
          <div key={i} className={className}>
            {line || "\u00A0"}
          </div>
        );
      })}
    </div>
  );
}
