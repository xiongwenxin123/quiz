.PHONY: test compile schema

test:
	PYTHONPATH=src python3 -m unittest discover -v

compile:
	python3 -m compileall -q src tests

schema:
	PYTHONPATH=src python3 -m polyglot_quiz.cli schema

