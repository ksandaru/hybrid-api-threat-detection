FROM python:3.13-slim

WORKDIR /usr/src/app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Dependencies first, so editing app.py does not trigger a full reinstall of
# scikit-learn and xgboost.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Models are bind-mounted at runtime rather than copied in; see
# docker-compose.yml. The directory is created so the mount has somewhere to
# land and the service can report a clear error if it is empty.
RUN mkdir -p models && useradd --create-home --uid 1001 mluser \
    && chown -R mluser:mluser /usr/src/app
USER mluser

EXPOSE 8000

# Readiness, not liveness: the service answers /health while artefacts are
# still loading, and reports ready=false until they are resident.
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=12 \
  CMD python -c "import json,sys,urllib.request; sys.exit(0 if json.load(urllib.request.urlopen('http://localhost:8000/health', timeout=3)).get('ready') else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
