// Same-origin proxy to the FastAPI backend. API_BASE_URL is read at request
// time, so one container image works in every environment.
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const API_BASE_URL = () => (process.env.API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const FORWARD_HEADERS = ["content-type", "accept", "x-request-id"];

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const url = `${API_BASE_URL()}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  for (const h of FORWARD_HEADERS) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }
  const hasBody = !["GET", "HEAD"].includes(req.method);
  try {
    const upstream = await fetch(url, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      cache: "no-store",
    });
    const out = new Headers();
    for (const h of ["content-type", "x-request-id"]) {
      const v = upstream.headers.get(h);
      if (v) out.set(h, v);
    }
    return new Response(upstream.body, { status: upstream.status, headers: out });
  } catch {
    return Response.json(
      {
        error: {
          code: "backend_unavailable",
          message: "The RippleOps analysis service is not reachable right now. Please try again in a moment.",
        },
      },
      { status: 503 },
    );
  }
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as PUT, proxy as DELETE };
