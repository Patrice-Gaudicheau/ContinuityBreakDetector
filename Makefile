.PHONY: test lint lint-basic format-check typecheck typecheck-basic quality clean-generated run-demo demo-study

test:
	python -m py_compile $$(find . -name "*.py")
	pytest -q

lint:
	ruff check .

lint-basic:
	python -m py_compile $$(find . -name "*.py")

format-check:
	ruff format --check .

typecheck-basic:
	@if command -v mypy >/dev/null 2>&1; then \
		mypy continuity_break_detector; \
	else \
		echo "mypy is not installed; skipping typecheck-basic"; \
	fi

typecheck:
	mypy continuity_break_detector

quality:
	python -m py_compile $$(find . -name "*.py")
	ruff check .
	mypy continuity_break_detector
	pytest -q

clean-generated:
	rm -rf data/raw data/processed studies/backtests studies/demo_study publication/paper
	rm -f *.sqlite *.db
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +

run-demo:
	@echo "Synthetic sample outputs are available under examples/:"
	@ls examples

demo-study:
	python main.py demo_study
