# Single image for both the FastAPI API and the arq worker.
# Override the command per service (uvicorn vs arq) at deploy time.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for lxml/trafilatura.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Default: run the API. Worker services override with: arq api.worker.WorkerSettings
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
