# syntax=docker/dockerfile:1.7
# PBI-001: multi-stage Dockerfile — node:22-alpine builder → nginx:alpine runtime
# Spec: specs/coolify-deploy/spec.md contracts 1,4,5 (static nginx, health, no secrets, <50MB)

FROM node:22-alpine AS builder
WORKDIR /app

# Install deps first for layer cache
COPY package.json package-lock.json* ./
RUN npm install --ignore-scripts || npm install

# Copy source
COPY . .

# Gates must still pass in builder (fail fast if docs invariants break)
RUN npm run build
RUN npm run lint
RUN npm test

# Assemble static site for nginx
# - public/index.html is the brand landing placeholder (already with #0D0D0D / #00FF41)
# - Copy docs + README as static files alongside
# - Create dist dir that nginx will serve
RUN mkdir -p /app/dist && \
    cp -r public/* /app/dist/ 2>/dev/null || cp public/index.html /app/dist/index.html && \
    mkdir -p /app/dist/docs && cp -r docs/* /app/dist/docs/ && \
    cp README.md /app/dist/README.md && \
    cp AGENTS.md /app/dist/AGENTS.md 2>/dev/null || true && \
    cp ARCHITECTURE.md /app/dist/ARCHITECTURE.md 2>/dev/null || true && \
    ls -lh /app/dist && echo "builder dist OK"

# --- Runtime ---
FROM nginx:alpine
# nginx:alpine is ~15MB; final image target <50MB compressed

# Remove default config and use ours
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy static site from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Ensure nginx user owns html + pid + cache (non-root runtime — guide: chown -R 1000:1000 for Paperclip /paperclip, here for nginx)
RUN mkdir -p /var/run /run /tmp && \
    chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d /var/run /run /tmp && \
    chmod -R 755 /usr/share/nginx/html && \
    # Validate nginx config at build time (fails the build if broken)
    nginx -t

# Document exposed port — 80 (running as root per fix, non-root requires pid /tmp and 8080 — see ADR-002)
EXPOSE 80

# Healthcheck — wget http://localhost/health → {"status":"ok"} (80, root)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/health | grep -q '"status":"ok"' || exit 1

# Run as root for now — non-root pid fix requires host volume chown like guide #5 (Paperclip /paperclip chown 1000:1000)
# TODO: re-enable USER nginx + pid /tmp/nginx.pid via sed on /etc/nginx/nginx.conf once host /run perms are handled
# USER nginx

# nginx runs in foreground
CMD ["nginx", "-g", "daemon off;"]
