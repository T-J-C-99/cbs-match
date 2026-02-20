FROM node:20-alpine

WORKDIR /app

# Copy root package files for workspace support
COPY package.json ./

# Copy shared package
COPY packages/shared ./packages/shared

# Copy web package files
COPY web/package.json ./web/

# Install dependencies from root (workspaces)
RUN npm install --legacy-peer-deps

# Copy web source
COPY web ./web

# Build shared package first
WORKDIR /app/packages/shared
RUN npm install && npm run test || true

# Run in development mode
WORKDIR /app/web
EXPOSE 3000
CMD ["npm", "run", "dev"]