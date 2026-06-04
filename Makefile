.PHONY: up down bootstrap train-all train-m1 train-m2 security-fast security-strict demo test evil-pickle

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
export PYTHONPATH := $(CURDIR)
-include .env
export
export MLFLOW_S3_ENDPOINT_URL ?= http://localhost:9000
export AWS_ACCESS_KEY_ID ?= minio
export AWS_SECRET_ACCESS_KEY ?= changeme
export AWS_DEFAULT_REGION ?= us-east-1

up:
	docker compose up -d --build

down:
	docker compose down

bootstrap:
	chmod +x scripts/*.sh gates/*.sh
	PYTHON=$(PYTHON) bash scripts/bootstrap.sh

evil-pickle:
	$(PYTHON) tests/fixtures/malicious/create_evil_pickle.py

train-m1: evil-pickle
	$(PYTHON) models/m1_scoring/train.py

train-m2:
	$(PYTHON) models/m2_antifraud/train.py

train-all: train-m1 train-m2

security-fast:
	PROFILE=fast PYTHON=$(PYTHON) bash scripts/run_gates.sh

security-strict:
	PROFILE=strict MODEL=m1 PYTHON=$(PYTHON) bash scripts/run_gates.sh
	G5_EXPECT_PASS=1 G5_TARGET=models/m1_scoring/artifact/onnx/model.onnx \
		gates/modelaudit.sh models/m1_scoring/artifact/onnx/model.onnx

demo:
	chmod +x scripts/demo.sh
	PYTHON=$(PYTHON) bash scripts/demo.sh

test:
	$(PYTHON) -m pytest tests/ -q

promote:
	@test -n "$(MODEL)" || (echo "MODEL=credit-scoring-pd VERSION=1 make promote"; exit 1)
	ACTOR_ROLE=mlsecops $(PYTHON) scripts/promote_to_production.py \
		--model $(MODEL) --version $(VERSION) --actor mlsecops1 --approve
	ACTOR_ROLE=mlsecops $(PYTHON) scripts/promote_to_production.py \
		--model $(MODEL) --version $(VERSION) --actor mlsecops1
