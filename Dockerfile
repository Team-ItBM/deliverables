# syntax=docker/dockerfile:1.7
#
# Stage 1 builds the SPA (web/). It runs on the build platform because the
# output is static files. With --build-arg SKIP_WEB=1, or when web/package.json
# is absent, it produces an empty dist so the server image still builds.
# In AWS the SPA is served from S3/CloudFront (deploy.yml builds and syncs it
# separately); the copy in this image is for local runs only.
FROM --platform=$BUILDPLATFORM node:22-slim AS web
ARG SKIP_WEB=0
WORKDIR /web
RUN --mount=type=bind,source=.,target=/ctx \
    mkdir -p /web/dist && \
    if [ "$SKIP_WEB" = "1" ] || [ ! -f /ctx/web/package.json ]; then \
      echo "Skipping web build (SKIP_WEB=$SKIP_WEB)"; \
    else \
      cp -R /ctx/web/. /web/ && npm ci && npm run build; \
    fi

# Stage 2: API server (FastAPI via uvicorn).
FROM python:3.13-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

RUN groupadd --system --gid 10001 app && \
    useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY src/ ./src/
# config/ is optional at this point of the project; copy it when present.
RUN --mount=type=bind,source=.,target=/ctx \
    if [ -d /ctx/config ]; then cp -R /ctx/config ./config; fi
COPY --from=web /web/dist ./web/dist

USER app
EXPOSE 8000

CMD ["uvicorn", "travel.server.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
