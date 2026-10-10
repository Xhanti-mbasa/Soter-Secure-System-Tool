FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SOTHIS_DATA=/var/lib/sothis
WORKDIR /app
COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt \
    && groupadd --gid 10001 sothis \
    && useradd --uid 10001 --gid 10001 --no-create-home sothis \
    && mkdir -p /var/lib/sothis && chown sothis:sothis /var/lib/sothis
COPY engine ./engine
COPY web ./web
COPY deploy/gunicorn.conf.py ./gunicorn.conf.py
COPY sources.json ./sources.json
COPY android/app/src/main/assets ./android/app/src/main/assets
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "--config", "gunicorn.conf.py", "web.app:create_app()"]
