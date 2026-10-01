# syntax=docker/dockerfile:1
#
# Print Service frontend — Vite/React build served by nginx, which also
# reverse-proxies the backend API/static/media paths. This container is the
# single ingress target for the cloudflared tunnel.
#
#   docker build -t printservice-frontend ./frontend
#
# The API base URL is baked at build time. The default "/api" keeps requests
# same-origin so nginx can proxy them and no CORS is needed.
FROM node:22-alpine AS build

WORKDIR /app

# Dependencies first so source edits don't bust the npm cache layer.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

########## runtime ###############################################################
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/ || exit 1
