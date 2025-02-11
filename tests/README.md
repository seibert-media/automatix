# TESTING

## Docker setup for integration tests

* Install docker and docker-compose
* Install pytest and pytest-docker via pip
  * If install fails, have a look at https://github.com/yaml/pyyaml/issues/601#issuecomment-1813963845
* Generate a ssh keypair and place it in tests with `ssh-keygen -t rsa -f tests/id_rsa_tests`
* In tests: Copy docker-compose.example.yml to docker-compose.yml and replace the public key
* Put something like the following in your ~/.ssh/config


    Host docker-test
      Hostname localhost
      Port 2222
      IdentityFile tests/id_rsa_tests
      StrictHostKeyChecking no
    

* Run `make test` in the automatix root directory.

Note: Testing remote commands on MacOs with podman seems broken (for me).
Maybe this needs some adjustment or further investigation.
