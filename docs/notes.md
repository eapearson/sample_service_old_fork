Setting up for local deployment and testing

create docker-compose to start up the sample service and all dependencies

install kafka locally and use clients to make sure kafka is working, using a local kafka docker-compose

need to set up the mock auth and workspace to properly support tests

for local usage, just need to have them cover how we are using the service

we can pass through auth and workspace to CI?

# Okay

so here is how it works at the moment:

- start up standalone mocks
    - In the mock repo (kbase-ui-mock-services)
    - docker run -v "$(pwd)/datasets/SampleService:/data" -p 3333:3333 --net kbase-dev --name mocker --rm mocker
- start up sample service, related services via docker-compose
    - docker-compose up

## Using pipenv on macOs

Annoying, since I'm used to the classic venv and pip installs.

- ensure that things are in your path:

on a fresh mac with Big Sur, you need to edit ~/.zprofile, the profile for zsh.

fix your path:
export PATH="/Users/erikpearson/Library/Python/3.7/bin:/Users/erikpearson/.local/bin:$PATH"

where the first path element is for python installed binaries, and the second is for pipx installed binaries (and other
tools may use this dir also)

- install pipx

pip install --user pipx

- install pipenv

pipx install pipenv

- install mypy

pipx install mypy

- install pytest

pipx install pytest

- using pipenv

for some reason I need to disable virtuaenvs; I don't know where pipenv is finding them

PIPENV_IGNORE_VIRTUALENVS=1 pipenv install --dev

and then perhaps

PIPENV_IGNORE_VIRTUALENVS=1 pipenv shell

wtf?

got mypy errors, needed to do `mypy --install-types`

needed pipenv install pytest-cov for using --cov with pytest

## AND MORE!

back to working on this again after a hiatus

the mock services are started with the docker compose, it looks like.

also, should explore proxying the whole thing to CI arango and services.

try:

```shell
export MOCK_DATASET_PATH=`pwd`/test/data/mock_services/SampleService
docker compose up
docker compose rm -sfv
```

or actually

```shell
export MOCK_DATASET_PATH=`pwd`/test/data/mock_services
make start-test-server
make remove-test-server
```


or really 


```shell
export MOCK_DATASET_PATH=`pwd`/test/data/mock_services
make host-test-integration
```