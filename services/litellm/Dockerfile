FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary pydantic
COPY fortress /app/fortress
COPY services/litellm /app/services/litellm
ENV PYTHONPATH=/app
CMD ["uvicorn", "services.litellm.app:app", "--host", "0.0.0.0", "--port", "4000"]
