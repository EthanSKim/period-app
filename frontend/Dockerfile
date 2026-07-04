# Base stage
FROM node:24-slim AS base

WORKDIR /app

# Development stage
FROM base AS development

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev"]

# Production builder stage
FROM base AS builder

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production server stage
FROM nginx:1.25-alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
