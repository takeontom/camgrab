format: yapf-format isort-format

lint: flake8-lint isort-lint

test-watch:
	ptw --onpass "py.test --cov=camgrab --cov-report=term-missing" -- --testmon

flake8-lint:
	flake8

isort-format:
	isort -rc --atomic .

isort-lint:
	isort -rc -c .

yapf-format:
	yapf -i -r --style .style.yapf .
