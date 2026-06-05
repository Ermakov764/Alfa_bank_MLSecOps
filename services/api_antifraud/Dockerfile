FROM python:3.11-slim
WORKDIR /app
COPY requirements-docker-api.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY fortress /app/fortress
COPY services/api_antifraud /app/services/api_antifraud
RUN mkdir -p /app/artifacts/models/m2_antifraud/onnx
ENV PYTHONPATH=/app
EXPOSE 8002
CMD ["uvicorn", "services.api_antifraud.app:app", "--host", "0.0.0.0", "--port", "8002"]
