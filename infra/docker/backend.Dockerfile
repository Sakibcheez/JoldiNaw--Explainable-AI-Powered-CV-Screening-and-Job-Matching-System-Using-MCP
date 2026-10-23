FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
RUN groupadd -r app && useradd -r -g app app && mkdir -p /app/storage /app/artifacts /app/data && chown -R app:app /app
COPY --chown=app:app backend /app/backend
COPY --chown=app:app ml /app/ml
ENV PYTHONPATH=/app/backend:/app
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
