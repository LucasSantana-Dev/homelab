ARG PAPERLESS_BASE_IMAGE=ghcr.io/paperless-ngx/paperless-ngx:latest
FROM ${PAPERLESS_BASE_IMAGE}

# Install Portuguese OCR language pack
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr-por && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
