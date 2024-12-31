# Build stage
FROM node:20-slim as builder

WORKDIR /app

# Copy package files
COPY website/package*.json ./
COPY website/yarn.lock ./

# Install dependencies
RUN yarn install --frozen-lockfile

# Development stage
FROM builder as development

# Set development environment
ENV NODE_ENV=development

# Mount points for volumes
VOLUME ["/app/website", "/app/node_modules"]

# Start development server
CMD ["yarn", "dev"]

# Production build stage
FROM builder as production-build

# Copy application code
COPY website .

# Build application
RUN yarn build

# Production stage
FROM node:20-slim as production

WORKDIR /app

# Copy only necessary files
COPY --from=production-build /app/package*.json ./
COPY --from=production-build /app/yarn.lock ./
COPY --from=production-build /app/dist ./dist
COPY --from=production-build /app/public ./public

# Install production dependencies only
RUN yarn install --production --frozen-lockfile

ENV NODE_ENV=production

CMD ["yarn", "start"]
