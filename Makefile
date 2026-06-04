# FORTRESS — all targets run via Docker (see ./fortress or fortress.ps1)
.PHONY: up down bootstrap train-all ci-pipeline demo test gates all help

help:
	@echo "Use: ./bin/fortress <command>   or   .\\fortress.ps1 <command>"
	@echo "  up bootstrap train pipeline demo test gates all down"

up:
	docker compose up -d --build

down:
	docker compose down

bootstrap:
	docker compose --profile tools run --rm fortress bootstrap

train-all train:
	docker compose --profile tools run --rm fortress train

ci-pipeline:
	docker compose --profile tools run --rm fortress pipeline

demo:
	docker compose --profile tools run --rm fortress demo

test:
	docker compose --profile tools run --rm fortress test

gates:
	docker compose --profile tools run --rm -e PROFILE=$(or $(PROFILE),fast) -e MODEL=$(or $(MODEL),m1) fortress gates

all:
	docker compose up -d --build postgres minio minio-init mlflow api-scoring api-antifraud litellm dashboard
	docker compose --profile tools run --rm fortress bootstrap
	docker compose --profile tools run --rm fortress train
	docker compose --profile tools run --rm fortress demo

evil-pickle:
	docker compose --profile tools run --rm fortress shell -c "python tests/fixtures/malicious/create_evil_pickle.py"

deploy-precheck:
	docker compose --profile tools run --rm fortress deploy-precheck

promote:
	@test -n "$(MODEL)" || (echo "MODEL=credit-scoring-pd VERSION=1 make promote"; exit 1)
	docker compose --profile tools run --rm -e ACTOR_ROLE=mlsecops fortress shell -c \
		"python scripts/promote_to_production.py --model $(MODEL) --version $(VERSION) --actor mlsecops1 --approve && \
		 python scripts/promote_to_production.py --model $(MODEL) --version $(VERSION) --actor mlsecops1"
