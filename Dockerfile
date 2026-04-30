FROM node:20-alpine AS frontend-build

WORKDIR /app/web-app/frontend

COPY web-app/frontend/package.json web-app/frontend/package-lock.json ./
RUN npm ci

COPY web-app/frontend/ ./
RUN npm run build


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NORMA_DATA_DIR=/data

WORKDIR /app

COPY pyproject.toml README.md ./
COPY norma_engine ./norma_engine
COPY ontology ./ontology
COPY regulations ./regulations
COPY camunda-template ./camunda-template
COPY web-app ./web-app
COPY --from=frontend-build /app/web-app/frontend/dist ./web-app/frontend/dist

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . \
    && pip install --no-cache-dir -r web-app/backend/requirements.txt

EXPOSE 8000

VOLUME ["/data"]

WORKDIR /app/web-app

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
