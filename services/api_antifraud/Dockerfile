FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn onnxruntime numpy psycopg2-binary mlflow pydantic
COPY fortress /app/fortress
COPY services/api_antifraud /app/services/api_antifraud
COPY artifacts/models/m2_antifraud /app/artifacts/models/m2_antifraud
ENV PYTHONPATH=/app
CMD ["uvicorn", "services.api_antifraud.app:app", "--host", "0.0.0.0", "--port", "8002"]
