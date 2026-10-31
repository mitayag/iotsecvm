FROM python:3.12.8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    IOTLAB_ALLOW_MUTATIONS=0

WORKDIR /srv/iotlab
COPY backend/requirements.txt /srv/iotlab/backend/requirements.txt
RUN pip install --no-cache-dir --disable-pip-version-check \
    -r /srv/iotlab/backend/requirements.txt

COPY VERSION /srv/iotlab/VERSION
COPY backend /srv/iotlab/backend
COPY frontend /srv/iotlab/frontend
COPY labs /srv/iotlab/labs
COPY schema /srv/iotlab/schema

RUN useradd --system --uid 10002 --no-create-home iotlab
USER 10002

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)"]

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
