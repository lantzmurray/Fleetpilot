FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent/ agent/
COPY harness/ harness/
COPY web/ web/
ENV PORT=8080
CMD exec uvicorn web.app:app --host 0.0.0.0 --port $PORT
