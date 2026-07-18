.PHONY: test demo build install
test:
	pytest -q
demo:
	python demo/run_demo.py
build:
	python -m build
install:
	pip install -e .[dev,llm]
