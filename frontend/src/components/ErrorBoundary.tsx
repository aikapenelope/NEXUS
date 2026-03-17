"use client";

import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Global error boundary that catches unhandled React errors and shows
 * a friendly fallback UI instead of the raw Next.js "Application Error"
 * screen.  The "Try again" button clears localStorage (which may contain
 * corrupted chat persistence data) and reloads the page.
 */
export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleReset = () => {
    try {
      localStorage.clear();
    } catch {
      // localStorage may be unavailable
    }
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center min-h-screen bg-zinc-950 px-4">
          <div className="max-w-md w-full text-center space-y-6">
            <div className="flex justify-center">
              <div className="p-4 bg-red-500/10 rounded-full">
                <AlertTriangle className="w-10 h-10 text-red-400" />
              </div>
            </div>

            <div className="space-y-2">
              <h1 className="text-xl font-semibold text-zinc-100">
                Something went wrong
              </h1>
              <p className="text-sm text-zinc-400">
                NEXUS encountered an unexpected error. This is usually caused
                by a browser extension, VPN, or corrupted local data.
              </p>
            </div>

            {this.state.error && (
              <pre className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-zinc-500 text-left overflow-x-auto max-h-24 overflow-y-auto">
                {this.state.error.message}
              </pre>
            )}

            <div className="flex flex-col items-center gap-3">
              <button
                onClick={this.handleReset}
                className="flex items-center gap-2 px-6 py-2.5 text-sm font-medium text-zinc-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Try again
              </button>
              <p className="text-xs text-zinc-600">
                This will clear cached data and reload the page.
              </p>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
