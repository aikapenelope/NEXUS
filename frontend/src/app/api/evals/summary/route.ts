import { NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://nexus-api:8000";

export async function GET() {
  const res = await fetch(`${API_BASE}/evals/summary`);
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
