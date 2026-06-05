FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://github.com/sigstore/cosign/releases/download/v2.4.1/cosign-linux-amd64 \
      -o /usr/local/bin/cosign \
    && chmod +x /usr/local/bin/cosign \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-docker-api.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY fortress /app/fortress
COPY services/api_antifraud /app/services/api_antifraud
RUN mkdir -p /app/artifacts/models/m2_antifraud/onnx
ENV PYTHONPATH=/app
EXPOSE 8002
CMD ["uvicorn", "services.api_antifraud.app:app", "--host", "0.0.0.0", "--port", "8002"]
