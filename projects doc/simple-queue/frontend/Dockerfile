# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps first (Docker layer cache optimization)
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# ── Stage 2: Serve ────────────────────────────────────────────────────────────
# Tiny nginx image serving only the static build output
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
