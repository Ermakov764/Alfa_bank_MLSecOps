FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir fastapi uvicorn onnxruntime numpy psycopg2-binary mlflow pydantic
COPY fortress /app/fortress
COPY services/api_scoring /app/services/api_scoring
COPY models/m1_scoring/artifact /app/models/m1_scoring/artifact
ENV PYTHONPATH=/app
CMD ["uvicorn", "services.api_scoring.app:app", "--host", "0.0.0.0", "--port", "8001"]
