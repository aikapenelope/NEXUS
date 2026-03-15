/** Proxy: GET /api/runs -> backend GET /runs */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_API_URL ?? "http://nexus-api:8000";

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const params = new URLSearchParams();
    const limit = searchParams.get("limit");
    const agentId = searchParams.get("agent_id");
    const source = searchParams.get("source");
    if (limit) params.set("limit", limit);
    if (agentId) params.set("agent_id", agentId);
    if (source) params.set("source", source);

    const qs = params.toString();
    const url = `${BACKEND_URL}/runs${qs ? `?${qs}` : ""}`;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ error: `Backend ${res.status}` }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
