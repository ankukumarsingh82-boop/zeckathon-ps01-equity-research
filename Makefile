PY=.venv/bin/python
setup:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.lock
all:
	$(PY) run_all.py
test:
	$(PY) -m pytest -q
app:
	.venv/bin/streamlit run app.py
refresh:
	PYTHONPATH=src $(PY) -m zk.refresh
