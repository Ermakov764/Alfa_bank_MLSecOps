FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir streamlit pandas psycopg2-binary mlflow pyyaml
COPY fortress /app/fortress
COPY dashboard /app/dashboard
COPY models /app/models
ENV PYTHONPATH=/app
EXPOSE 8501
CMD ["streamlit", "run", "dashboard/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
