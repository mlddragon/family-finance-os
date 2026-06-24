FROM node:26-slim AS web-build
ENV NPM_CONFIG_AUDIT=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_LOGLEVEL=error \
    NPM_CONFIG_UPDATE_NOTIFIER=false
WORKDIR /app/apps/web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.14-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_ROOT=/data \
    APP_BIND_HOST=127.0.0.1 \
    APP_ENV=personal \
    APP_ENV_LABEL="Personal data" \
    DATASET_KIND=personal \
    DEV_MODE=false

WORKDIR /app
RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --home-dir /app --shell /usr/sbin/nologin appuser

COPY pyproject.toml ./
COPY apps/api ./apps/api
COPY --from=web-build /app/apps/web/dist ./apps/api/family_finance_os/static
RUN pip install --no-cache-dir --root-user-action=ignore .

USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "family_finance_os.main:app", "--host", "0.0.0.0", "--port", "8080"]
