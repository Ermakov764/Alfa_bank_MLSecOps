FROM python:3.11-slim
WORKDIR /app
COPY requirements-docker-dashboard.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY fortress /app/fortress
COPY dashboard /app/dashboard
COPY scripts /app/scripts
COPY data /app/data
COPY models /app/models
ENV PYTHONPATH=/app
ENV ARTIFACTS_DIR=/app/artifacts
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')" || exit 1
CMD ["streamlit", "run", "dashboard/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
