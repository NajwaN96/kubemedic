FROM python:3.12-slim AS build

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY --from=build /install /usr/local
WORKDIR /app
COPY app ./app

USER appuser
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
