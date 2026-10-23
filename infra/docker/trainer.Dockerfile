FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.lock /tmp/runtime.lock
RUN pip install --no-cache-dir -r /tmp/runtime.lock datasets==5.1.0 sentence-transformers==6.2.0
RUN useradd -m trainer && mkdir -p /app/data /app/artifacts /app/ml/reports && chown -R trainer:trainer /app
COPY --chown=trainer:trainer ml /app/ml
COPY --chown=trainer:trainer backend/app /app/backend/app
ENV PYTHONPATH=/app:/app/backend
USER trainer
CMD ["python", "-m", "ml.pipeline", "--help"]
