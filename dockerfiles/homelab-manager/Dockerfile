FROM python:3.11-slim

WORKDIR /app

# Copy package metadata and source
COPY pyproject.toml README.md ./
COPY homelab_manager/ ./homelab_manager/

# Install dependencies at build time (not runtime)
RUN pip install --no-cache-dir --target /app/site-packages .

# Set Python path and ensure unbuffered output
ENV PYTHONPATH=/app/site-packages
ENV PYTHONUNBUFFERED=1

EXPOSE 8765

# Health check using stdlib urllib (curl not available in slim base)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=60s \
  CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8765/health', timeout=5).status == 200 else 1)"

CMD ["python", "-m", "homelab_manager", "serve", "--host", "0.0.0.0", "--port", "8765"]
