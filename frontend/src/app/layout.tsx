"use client";

import "./globals.css";
import "@copilotkit/react-ui/styles.css";
import { CopilotKit } from "@copilotkit/react-core";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        <ErrorBoundary>
          <CopilotKit
            runtimeUrl="/api/copilotkit"
            agent="nexus_copilot"
          >
            {children}
          </CopilotKit>
        </ErrorBoundary>
      </body>
    </html>
  );
}
