# GOPHER AI — python hole (server.py). Stdlib only.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin gopher

WORKDIR /app

COPY --chown=gopher:gopher . /app

# Free hosts inject PORT; default 8080 for containers.
ENV PORT=8080
ENV GOPHER_HOST=0.0.0.0
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

USER gopher

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

CMD ["python3", "server.py"]
