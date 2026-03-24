"use client";

interface FileTreeProps {
  files: string[];
}

/**
 * Simple file tree showing changed/created files.
 */
export function FileTree({ files }: FileTreeProps) {
  if (files.length === 0) {
    return (
      <div className="p-3 text-xs text-zinc-600 text-center mt-4">
        No files changed
      </div>
    );
  }

  return (
    <div className="p-3 space-y-1">
      {files.map((file, i) => (
        <div
          key={i}
          className="flex items-center gap-2 text-xs font-mono text-zinc-300 px-2 py-1 rounded bg-zinc-900/50"
        >
          <span className="text-emerald-500">+</span>
          <span>{file}</span>
        </div>
      ))}
    </div>
  );
}
