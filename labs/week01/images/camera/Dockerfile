FROM python:3.12.8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 camera \
    && useradd --uid 10001 --gid camera --no-create-home \
       --home-dir /app --shell /usr/sbin/nologin camera \
    && mkdir -p /app /state /evidence \
    && chown -R 10001:10001 /app /state /evidence

WORKDIR /app
COPY app.py /app/app.py

USER 10001
EXPOSE 8080 8554

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"]

CMD ["python", "/app/app.py"]
