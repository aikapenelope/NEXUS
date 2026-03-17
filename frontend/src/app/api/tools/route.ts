import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://nexus-api:8000";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const category = searchParams.get("category");
  const qs = category ? `?category=${category}` : "";
  const res = await fetch(`${API_BASE}/tools${qs}`);
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
