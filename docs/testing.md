# Testing

Sample service tests are divided into unit and integration tests.

Unit tests require no specific runtime resources, other than files in the repo. The unit tests are located in `test/unit` and generate coverage in `test/


Running the tests:

## Overall

```bash
make host-tests
```

which takes care of clearing the coverage, running all tests, and compiling the html coverage report.

## unit tests

Unit tests may be run in a standalone container. We can use the service image for this. We specify the "unit-test" option, which causes the entrypoint script to run the unit tests.

```bash
docker compose -f docker-compose-unit-test.yml run sampleservice
```

## integration tests

Integration tests must run with both the source code available, and a running sample service with all dependent services.

This is accomplished by running the test server stack (docker-compose.yml) and invoking "run" for a secondary sample service container.

In other words, one sample service container is running the service, another is just running the integration tests.

This is required

```shell
export MOCK_DATASET_PATH=`pwd`/test/data/mock_services
```

in order to let the tests know where to find the mock services data (for the mock services) in the docker compose.

