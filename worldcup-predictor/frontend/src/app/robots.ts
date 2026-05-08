import type { MetadataRoute } from 'next';

/**
 * Robots policy. We disallow crawling of the auth + admin + protected
 * paths because they're either personalised or operator-only — the public
 * pricing / track-record / worldcup pages stay open. The sitemap pointer
 * lets crawlers discover the canonical list without guessing.
 */
export default function robots(): MetadataRoute.Robots {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://wcp.example.com';
  return {
    rules: [
      {
        userAgent: '*',
        allow: ['/'],
        disallow: ['/admin', '/admin/', '/login', '/profile', '/notifications'],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
    host: base,
  };
}
