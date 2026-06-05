FROM python:3.11-slim
WORKDIR /app
COPY requirements-llm.txt /tmp/requirements-llm.txt
RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary pydantic joblib scikit-learn \
    -r /tmp/requirements-llm.txt
COPY fortress /app/fortress
COPY services/litellm /app/services/litellm
COPY models/m3_nlp/artifact /app/models/m3_nlp/artifact
ENV PYTHONPATH=/app
ENV M3_MODEL_PATH=/app/models/m3_nlp/artifact/intent_pipeline.joblib
CMD ["uvicorn", "services.litellm.app:app", "--host", "0.0.0.0", "--port", "4000"]
