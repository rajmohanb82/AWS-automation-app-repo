# Render web service image. Build from the repository root:
#   docker build -f render/Dockerfile -t cloudsync-render .
# Render.com sets this service's build context to the repository root
# and this file as the Dockerfile. It does not use docker-compose.yml.

FROM python:3.12-slim-bookworm

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin app

WORKDIR /app

COPY portal/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt gunicorn \
    && rm /tmp/requirements.txt

# Application source only. portal/data (the local database) is never copied into the image.
COPY portal/*.py /app/
COPY portal/engine/ /app/engine/
COPY portal/static/ /app/static/
COPY portal/templates/ /app/templates/
RUN mkdir -p /var/data && chown -R app:app /app /var/data

COPY render/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

ENV HOME=/home/app \
    HOST=0.0.0.0 \
    PORTAL_DB=/var/data/portal.db \
    PYTHONUNBUFFERED=1

EXPOSE 10000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 8 --timeout 180 --graceful-timeout 30 --access-logfile - --error-logfile - run:app"]
