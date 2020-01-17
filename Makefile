default: test

test:
	@pytest --docker-compose=tests/docker-compose.yml
