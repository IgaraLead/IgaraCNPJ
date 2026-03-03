# ── Dev (Vite dev server com proxy + hot-reload) ──
FROM node:20-alpine AS dev
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ENV VITE_API_TARGET=http://backend:8000
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ── Build ──
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# ── Serve (produção) ──
FROM node:20-alpine
RUN npm install -g serve@latest
WORKDIR /app
COPY --from=build /app/dist ./dist
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
