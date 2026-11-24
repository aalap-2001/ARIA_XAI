# ---- build the web app
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- runtime
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ARIAX_ENV=production ARIAX_DATA_DIR=/data
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY ariax/ ariax/
COPY backend/app/ backend/app/
COPY --from=web /web/dist frontend/dist
RUN useradd --create-home --uid 10001 ariax && mkdir -p /data && chown ariax /data
USER ariax
VOLUME /data
EXPOSE 8700
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8700/healthz')"
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8700", "--proxy-headers", "--forwarded-allow-ips", "*"]
