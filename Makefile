test-watch:
	ptw --onpass "py.test --cov=camgrab --cov-report=term-missing" -- --testmon
