# Local Docker Development and Deployment

Due to the sample service's dependencies on other services (Arango DB, Kafka, Zookeeper, and KBase's auth and workspace), it can be rather complex, time-consuming, and unreliable to install and run these dependencies on the host machine.

To ease this burden, you may use a docker-compose based workflow.

This workflow:

- runs real external 3rd party services in containers (Arango, Kafka, Zookeeper)
- runs mock KBase services

Here is the basic workflow:

```shell
export MOCK_DATASET_PATH=`pwd`/data/test/SampleService
# export GITHUB_TOKEN=YOUR_GITHUB_PAT
# export SPECS_GITHUB_REPO=eapearson/sample_service_validator_config
# export SPECS_GITHUB_BRANCH=dist-pull_request-7
make start-dev-server
```

After a few seconds, you should have an operational Sample Service running on http://localhost:5000.

To close up shop, halt the services with `Ctrl-C` and issue:

```shell
docker compose rm -sfv
```

to clean up the containers.

## Status

This currently works for methods which do not access ArangoDB. That excludes most of the API, so we have work to do!. Primarily, the database needs to be populated with example data, and supporting mock data for the workspace and auth as well.
