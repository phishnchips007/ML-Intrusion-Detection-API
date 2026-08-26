# Verified with `docker buildx imagetools inspect` on 2026-08-26.
# The index digest keeps the current Python 3.11.16 slim Trixie image portable
# across supported Docker platforms while fixing the patch release and image.
FROM python:3.11.16-slim-trixie@sha256:be1575ed968de893bd54f4c56315ff7c4736ce522c1bca08fd521731aafc0d76

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --requirement requirements.txt \
    && python -m pip uninstall --yes setuptools wheel pip \
    && addgroup --system app \
    && adduser --system --ingroup app app

COPY --chown=app:app app/ ./app/
COPY --chown=app:app model/ ./model/

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
