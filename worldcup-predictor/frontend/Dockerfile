# Multi-stage build: Next.js standalone output + a slim runtime image.

# --- Build stage ----------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps in a separate layer so a code-only change doesn't reinstall.
COPY package.json package-lock.json* ./
RUN npm ci

# Copy the rest of the source and build.
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- Runtime stage --------------------------------------------------------
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# next.config.mjs sets `output: 'standalone'`, so we copy the trimmed bundle
# + the public assets and skip a full node_modules install.
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Run as non-root.
RUN addgroup -S nextjs && adduser -S nextjs -G nextjs && chown -R nextjs:nextjs /app
USER nextjs

EXPOSE 3000
CMD ["node", "server.js"]
