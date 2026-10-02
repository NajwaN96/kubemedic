FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    KUBEMEDIC_DB_PATH=/data/kubemedic.db

WORKDIR /app

RUN useradd --uid 10002 --create-home --shell /usr/sbin/nologin kubemedic \
    && pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY fixtures ./fixtures
RUN mkdir -p /data && chown -R kubemedic:kubemedic /app /data

USER 10002

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
