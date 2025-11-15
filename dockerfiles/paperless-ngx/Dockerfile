FROM ghcr.io/paperless-ngx/paperless-ngx:latest

# Install Portuguese OCR language pack
RUN apt-get update && \
    apt-get install -y tesseract-ocr-por && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
