import type { MetadataRoute } from 'next';

/**
 * Sitemap for crawlers. Lists the curated public surfaces — match-detail
 * pages are skipped here because there are 100+ of them and they share an
 * identical priority. The /worldcup/* routes give crawlers a path into the
 * graph without us shipping a 100-row XML for every fixture.
 *
 * Returned every request (no caching) — the list is small enough that
 * computing it on demand is cheaper than maintaining cache invalidation
 * around fixture additions.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://wcp.example.com';
  const lastModified = new Date();
  const routes = [
    { path: '/', priority: 1.0, changeFrequency: 'hourly' as const },
    { path: '/track-record', priority: 0.9, changeFrequency: 'daily' as const },
    { path: '/worldcup/groups', priority: 0.8, changeFrequency: 'daily' as const },
    { path: '/worldcup/bracket', priority: 0.8, changeFrequency: 'daily' as const },
    { path: '/worldcup/simulation', priority: 0.7, changeFrequency: 'daily' as const },
    { path: '/subscribe', priority: 0.6, changeFrequency: 'weekly' as const },
    { path: '/about', priority: 0.4, changeFrequency: 'monthly' as const },
    { path: '/terms', priority: 0.2, changeFrequency: 'yearly' as const },
    { path: '/privacy', priority: 0.2, changeFrequency: 'yearly' as const },
  ];
  return routes.map((r) => ({
    url: `${base}${r.path}`,
    lastModified,
    changeFrequency: r.changeFrequency,
    priority: r.priority,
  }));
}
