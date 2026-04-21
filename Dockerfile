FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

COPY . /app

RUN mkdir -p /app/data/processed

EXPOSE 8080

CMD ["python", "scripts/run_server.py", "--host", "0.0.0.0", "--port", "8080", "--db", "data/processed/ptsd_support.db"]
