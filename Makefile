VENV_DIR ?= .venv
PYTHON ?= $(VENV_DIR)/bin/python
LOCAL_PYTHONPATH := packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src

.PHONY: setup test demo env-check clean-runtime

setup:
	python3 -m venv $(VENV_DIR)
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -q tests

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
