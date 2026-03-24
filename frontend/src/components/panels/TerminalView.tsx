"use client";

import { useEffect, useRef } from "react";

interface TerminalViewProps {
  output: string;
}

/**
 * Simple terminal-style output viewer.
 * Shows execute tool output with monospace font and dark background.
 * Auto-scrolls to bottom as new output arrives.
 */
export function TerminalView({ output }: TerminalViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [output]);

  if (!output) {
    return (
      <div className="p-3 text-xs text-zinc-600 text-center mt-4">
        No terminal output yet
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="h-full overflow-y-auto bg-zinc-950 p-3 font-mono text-xs text-green-400 leading-relaxed"
    >
      <pre className="whitespace-pre-wrap">{output}</pre>
    </div>
  );
}
