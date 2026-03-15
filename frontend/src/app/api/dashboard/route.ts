/** Proxy: GET /api/dashboard -> backend GET /dashboard/stats */
import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_API_URL ?? "http://nexus-api:8000";

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/dashboard/stats`, { cache: "no-store" });
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
