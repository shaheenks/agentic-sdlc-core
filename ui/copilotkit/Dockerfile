# Build context: repo root (docker build -f ui/copilotkit/Dockerfile .). See docker-compose.yml.
# CopilotKit chat app (version-01 M5), served behind oauth2-proxy at /chat. Talks AG-UI to the
# agent's internal /agui endpoint (SDLC_AGUI_URL); holds no secrets and stores no conversations.
FROM node:24-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY ui/copilotkit/package.json ui/copilotkit/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/copilotkit/ ./
RUN npm run build

FROM node:24-slim
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    NEXT_TELEMETRY_DISABLED=1 \
    COPILOTKIT_TELEMETRY_DISABLED=true \
    DO_NOT_TRACK=1
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER node
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --retries=6 \
  CMD node -e "fetch('http://127.0.0.1:3000/chat/api/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
