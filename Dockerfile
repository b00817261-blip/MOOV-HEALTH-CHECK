# Portable container for the MOOV Health Check website.
# Works anywhere that runs a container with a public port: Render, Railway,
# Fly.io, Google Cloud Run, a plain VM, etc. The app binds to $PORT.
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .

# The platform provides $PORT; the app reads it. Data lives in $MOOV_DATA_DIR
# (mount a volume there on hosts that support one, to persist between deploys).
ENV PORT=8000 \
    MOOV_DATA_DIR=/app/reports

EXPOSE 8000
CMD ["sh", "-c", "mkdir -p \"$MOOV_DATA_DIR\" && moov-health-check serve"]
