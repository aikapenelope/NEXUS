import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://nexus-api:8000";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const params = new URLSearchParams();
  const limit = searchParams.get("limit");
  const agentId = searchParams.get("agent_id");
  if (limit) params.set("limit", limit);
  if (agentId) params.set("agent_id", agentId);

  const qs = params.toString();
  const url = `${API_BASE}/evals${qs ? `?${qs}` : ""}`;
  const res = await fetch(url);
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
