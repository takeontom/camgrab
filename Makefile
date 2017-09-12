format: yapf-format isort-format

lint: flake8-lint isort-lint yapf-lint

test: pytest-test

test-watch:
	ptw --onpass "py.test --cov=camgrab --cov-report=term-missing" -- --testmon

pytest-test:
	py.test --cov=camgrab --cov-report=term-missing

flake8-lint:
	flake8

isort-format:
	isort -rc --atomic .

isort-lint:
	isort -rc -c .

yapf-format:
	yapf -i -r --style .style.yapf .

yapf-lint:
	yapf -d -r --style .style.yapf .
