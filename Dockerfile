FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
COPY agent/ agent/
COPY harness/ harness/
COPY web/ web/
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
ENV PORT=8080
CMD ["sh", "-c", "exec uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
