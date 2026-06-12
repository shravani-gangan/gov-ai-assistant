.PHONY: setup run test lint clean demo

setup:
	pip install -e ".[dev]"
	bash scripts/setup_models.sh
	docker-compose up -d chromadb redis

run:
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

lint:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

demo:
	python scripts/run_demo.py

clean:
	find . -type d -name __pycache__ | xargs rm -rf
	find . -type f -name "*.pyc" -delete