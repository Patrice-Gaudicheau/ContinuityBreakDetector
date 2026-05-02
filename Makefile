.PHONY: test lint-basic typecheck-basic clean-generated run-demo

test:
	python -m py_compile $$(find . -name "*.py")
	pytest -q

lint-basic:
	python -m py_compile $$(find . -name "*.py")

typecheck-basic:
	@if command -v mypy >/dev/null 2>&1; then \
		mypy continuity_break_detector; \
	else \
		echo "mypy is not installed; skipping typecheck-basic"; \
	fi

clean-generated:
	rm -rf data/raw data/processed studies/backtests publication/paper
	rm -f *.sqlite *.db
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +

run-demo:
	python main.py list_forecasters
	@echo "Synthetic sample outputs are available under examples/."

