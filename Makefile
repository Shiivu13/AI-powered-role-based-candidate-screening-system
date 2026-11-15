PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: install kb api web test bench

install:            ## create venv + install backend and frontend dependencies
	python3 -m venv .venv
	$(PIP) install -r backend/requirements-dev.txt
	cd frontend && npm install

kb:                 ## download the books and build the vector knowledge base
	cd backend && ../$(PY) -m scripts.download_kb; ../$(PY) -m scripts.ingest_kb && ../$(PY) -m scripts.export_kb

api:                ## run the FastAPI backend on :8000
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000

web:                ## run the React frontend on :5173
	cd frontend && npm run dev

test:               ## backend tests + frontend type-check/build
	cd backend && ../$(PY) -m pytest -q
	cd frontend && npm run build

bench:              ## retrieval benchmark (strategies + chunk-size ablation) -> docs/benchmarks/
	cd backend && ../$(PY) -m scripts.benchmark_retrieval --chunk-sizes 500 1000 1500
