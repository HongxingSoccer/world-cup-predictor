// Liveness probe for the Next.js standalone server.
//
// `force-static` lets Next pre-render this once at build time so it
// answers without going through any of the dynamic route plumbing
// (cookies / SSR cache / etc.). `no-store` keeps the response out of
// any upstream CDN cache so a 500 from this pod actually means this pod
// is in trouble — not a stale 200 served from edge.

export const dynamic = 'force-static';

export async function GET() {
  return new Response(
    JSON.stringify({ status: 'ok', service: 'wcp-frontend' }),
    {
      status: 200,
      headers: {
        'content-type': 'application/json',
        'cache-control': 'no-store',
      },
    },
  );
}
