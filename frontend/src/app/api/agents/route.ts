/**
 * Proxy route: GET /api/agents -> backend GET /agents
 *
 * The browser cannot reach the Docker-internal nexus-api hostname,
 * so this Next.js API route proxies the request server-side.
 */
import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_API_URL ?? "http://nexus-api:8000";

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/agents`, {
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json(
        { error: `Backend returned ${res.status}` },
        { status: res.status }
      );
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
