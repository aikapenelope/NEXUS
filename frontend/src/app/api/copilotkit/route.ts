/**
 * CopilotKit API route — bridges the Next.js frontend to the NEXUS
 * backend AG-UI endpoint via the CopilotKit runtime.
 */
import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { NextRequest } from "next/server";

/** Backend AG-UI endpoint (docker-compose internal network). */
const BACKEND_URL =
  process.env.BACKEND_COPILOT_URL ?? "http://nexus-api:8000/api/copilot";

const agent = new HttpAgent({ url: BACKEND_URL });

const runtime = new CopilotRuntime({
  agents: {
    nexus_copilot: agent,
  },
});

const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
  runtime,
  serviceAdapter: new ExperimentalEmptyAdapter(),
  endpoint: "/api/copilotkit",
});

export async function POST(req: NextRequest) {
  return handleRequest(req);
}
