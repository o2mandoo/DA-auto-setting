VENV_DIR ?= .venv
PYTHON ?= $(VENV_DIR)/bin/python
RELEASE_ID ?= release-$(shell date -u +%Y%m%dT%H%M%SZ)
RELEASE_OUT ?= reports/release
N8N_IMAGE ?= n8nio/n8n:2.19.5
N8N_LIVE_OUT ?= runtime/n8n_live_smoke/latest
LOCAL_PYTHONPATH := packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src

.PHONY: setup test lint ci demo env-check clean-runtime release-pack release-test n8n-live-smoke

setup:
	python3 -m venv $(VENV_DIR)
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -q tests

lint:
	$(PYTHON) -m ruff check packages scripts tests

ci: env-check test lint
	$(PYTHON) scripts/setup/clone_ready_setup.py
	bash scripts/setup/env_check.sh
	$(PYTHON) -m unittest discover -s tests/packaging -v

demo:
	$(PYTHON) -m semantic_builder.cli scan --source examples/demo_data --out runtime/phase12_demo/scan_report.json
	$(PYTHON) -m semantic_builder.cli profile --scan runtime/phase12_demo/scan_report.json --out runtime/phase12_demo/column_profiles.jsonl
	$(PYTHON) -m semantic_builder.cli infer-semantics --profiles runtime/phase12_demo/column_profiles.jsonl --hypotheses-out runtime/phase12_demo/semantic_hypotheses.jsonl --questions-out runtime/phase12_demo/onboarding_questions.jsonl
	$(PYTHON) -m semantic_builder.cli build-pack --profiles runtime/phase12_demo/column_profiles.jsonl --semantic-hypotheses runtime/phase12_demo/semantic_hypotheses.jsonl --onboarding-questions runtime/phase12_demo/onboarding_questions.jsonl --out runtime/phase12_demo/semantic_pack.draft.yaml
	@printf 'Demo artifacts written to runtime/phase12_demo\n'

env-check:
	PYTHONPATH=$(LOCAL_PYTHONPATH) $(PYTHON) -c 'import importlib, sys; [importlib.import_module(name) for name in ("semantic_contracts", "semantic_builder", "semantic_registry", "semantic_mcp")]; print(f"environment ok: {sys.version.split()[0]}")'

clean-runtime:
	rm -rf runtime/phase12_demo runtime/hardening_feedback

release-pack:
	$(PYTHON) scripts/release/build_release_packet.py --release-id $(RELEASE_ID) --out $(RELEASE_OUT)

release-test:
	$(PYTHON) -m pytest -q tests/release


n8n-live-smoke:
	$(PYTHON) scripts/n8n/live_runtime_smoke.py --image $(N8N_IMAGE) --out $(N8N_LIVE_OUT)
