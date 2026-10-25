FROM python:3.12-slim-bookworm

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data && chown -R app:app /app

USER app
ENV HOME=/home/app \
    HOST=0.0.0.0 \
    PORT=5080 \
    PORTAL_DB=/app/data/portal.db \
    PYTHONUNBUFFERED=1

EXPOSE 5080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5080/healthz')"

CMD ["python", "run.py"]
