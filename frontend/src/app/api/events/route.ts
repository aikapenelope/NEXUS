import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://nexus-api:8000";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const params = new URLSearchParams();
  const limit = searchParams.get("limit");
  const agentName = searchParams.get("agent_name");
  const eventType = searchParams.get("event_type");
  if (limit) params.set("limit", limit);
  if (agentName) params.set("agent_name", agentName);
  if (eventType) params.set("event_type", eventType);

  const qs = params.toString();
  const url = `${API_BASE}/events${qs ? `?${qs}` : ""}`;
  const res = await fetch(url);
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
