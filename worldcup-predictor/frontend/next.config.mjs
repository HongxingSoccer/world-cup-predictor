/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // `output: 'standalone'` produces a self-contained server bundle the
  // Dockerfile copies into the runtime stage — no node_modules needed at run-time.
  output: 'standalone',
  images: {
    // Team crests / share-card thumbnails come from MinIO + the Java service.
    remotePatterns: [
      { protocol: 'http', hostname: 'localhost' },
      { protocol: 'http', hostname: 'minio' },
      { protocol: 'http', hostname: 'java-api' },
      { protocol: 'https', hostname: '**.wcp.app' },
    ],
  },
  experimental: {
    typedRoutes: true,
  },
};

export default nextConfig;
