/**
 * Proxy routes: DELETE /api/workflows/[id] -> backend DELETE /workflows/[id]
 */
import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_API_URL ?? "http://nexus-api:8000";

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const res = await fetch(`${BACKEND_URL}/workflows/${id}`, {
      method: "DELETE",
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
