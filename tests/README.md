# TESTING

## Docker setup for integration tests

* Install docker and docker-compose.

Tipp: You can use podman (instead of docker) for testing remote commands on MacOS.
Install `podman-compose` via pip and symlink the `docker` command to `podman`.

* Install pytest and pytest-docker via pip
  * If install fails, have a look at https://github.com/yaml/pyyaml/issues/601#issuecomment-1813963845
* Create secrets directory with `mkdir -p tests/secrets`
* Generate a ssh keypair and place it in tests/secrets with `ssh-keygen -t rsa -f tests/secrets/id_rsa_tests`
* Put something like the following in your ~/.ssh/config


    Host docker-test
      Hostname localhost
      Port 2222
      IdentityFile tests/secrets/id_rsa_tests
      StrictHostKeyChecking no
    

* Run `make test` in the automatix root directory.
