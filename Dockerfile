# Stage 1: Build Frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

ARG VITE_API_URL
ARG VITE_COLLEGE_PHONE
ARG VITE_COLLEGE_EMAIL
ARG VITE_COLLEGE_NAME
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_COLLEGE_PHONE=$VITE_COLLEGE_PHONE
ENV VITE_COLLEGE_EMAIL=$VITE_COLLEGE_EMAIL
ENV VITE_COLLEGE_NAME=$VITE_COLLEGE_NAME

COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Build Backend and serve Frontend
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY backend/ .

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Use the PORT environment variable provided by Railway, defaulting to 8000
ENV PORT=8000
EXPOSE ${PORT}

# Run application using the dynamic port
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
