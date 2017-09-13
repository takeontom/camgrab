format: yapf-format isort-format

lint: flake8-lint isort-lint yapf-lint dist-check

test: pytest-test

test-watch:
	ptw --onpass "py.test --cov=camgrab --cov-report=term-missing" -- --testmon

clean: build-clean python-clean pytest-clean tox-clean

release: dist ## package and upload a release
	twine upload dist/*

dist: dist-check clean ## builds source and wheel package
	python setup.py sdist
	python setup.py bdist_wheel
	ls -l dist

dist-check:
	python setup.py check -mrs

build-clean:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

readme-html:
	rst2html README.rst > /tmp/camgrab-readme.html

readme-browser: readme-html
	xdg-open "file:///tmp/camgrab-readme.html"

readme-watch:
	watchmedo shell-command --pattern="./README.rst" --command="make readme-html" .

python-clean:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

pytest-test:
	py.test --cov=camgrab --cov-report=term-missing

pytest-clean:
	rm -f .coverage
	rm -fr htmlcov/
	rm -rf .tmontmp
	rm -f .testmondata
	rm -f .testmondata-journal
	rm -rf .cache

flake8-lint:
	flake8

isort-format:
	isort -rc --atomic camgrab tests setup.py

isort-lint:
	isort -rc -df -c camgrab tests setup.py

yapf-format:
	yapf -i -r --style .style.yapf -p camgrab tests setup.py

yapf-lint:
	yapf -d -r --style .style.yapf -p camgrab tests setup.py

tox-test:
	tox -r

tox-clean:
	rm -rf .tox
