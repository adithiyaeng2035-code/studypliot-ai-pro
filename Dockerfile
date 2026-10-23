FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STUDYPILOT_DATA_DIR=/data

WORKDIR /app
COPY requirements-prod.txt ./requirements-prod.txt
RUN python -m pip install --no-cache-dir -r requirements-prod.txt \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin studypilot \
    && mkdir -p /data \
    && chown -R studypilot:studypilot /data

COPY --chown=studypilot:studypilot app ./app
COPY --chown=studypilot:studypilot frontend ./frontend

USER studypilot
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["python", "-m", "uvicorn", "app.api.routes:app", "--host", "0.0.0.0", "--port", "8000"]
