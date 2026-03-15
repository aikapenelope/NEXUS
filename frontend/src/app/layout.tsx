"use client";

import "./globals.css";
import "@copilotkit/react-ui/styles.css";
import { CopilotKit } from "@copilotkit/react-core";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        <CopilotKit
          runtimeUrl="/api/copilotkit"
          agent="nexus_copilot"
        >
          {children}
        </CopilotKit>
      </body>
    </html>
  );
}
