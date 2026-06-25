PERSONAL_DATA_ROOT ?= $(HOME)/FamilyFinanceOS_Data
QA_DATA_ROOT ?= $(HOME)/FamilyFinanceOS_QA_Data
QA_SCENARIO ?= baseline

.PHONY: personal-up personal-down qa-up qa-down qa-seed qa-reset qa-update qa-deploy

qa-update qa-deploy:
	./scripts/qa_deploy.sh

personal-up:
	mkdir -p "$(PERSONAL_DATA_ROOT)"
	FFOS_HOST_PORT=28080 \
	FFOS_DATA_ROOT="$(PERSONAL_DATA_ROOT)" \
	APP_ENV=personal \
	APP_ENV_LABEL="Personal data" \
	DATASET_KIND=personal \
	DEV_MODE=false \
	docker compose -p ffos-personal up -d --build

personal-down:
	FFOS_DATA_ROOT="$(PERSONAL_DATA_ROOT)" docker compose -p ffos-personal down --remove-orphans

qa-up:
	mkdir -p "$(QA_DATA_ROOT)"
	FFOS_HOST_PORT=28081 \
	FFOS_DATA_ROOT="$(QA_DATA_ROOT)" \
	APP_ENV=qa \
	APP_ENV_LABEL="QA synthetic demo" \
	DATASET_KIND=synthetic \
	DEV_MODE=true \
	docker compose -p ffos-qa up -d --build

qa-down:
	FFOS_DATA_ROOT="$(QA_DATA_ROOT)" docker compose -p ffos-qa down --remove-orphans

qa-seed:
	APP_ENV=qa \
	APP_ENV_LABEL="QA synthetic demo" \
	DATASET_KIND=synthetic \
	DEV_MODE=true \
	.venv/bin/python scripts/qa_seed.py --scenario "$(QA_SCENARIO)" --data-root "$(QA_DATA_ROOT)"

qa-reset:
	APP_ENV=qa \
	APP_ENV_LABEL="QA synthetic demo" \
	DATASET_KIND=synthetic \
	DEV_MODE=true \
	.venv/bin/python scripts/qa_reset.py --data-root "$(QA_DATA_ROOT)" --confirm "$(CONFIRM)"
