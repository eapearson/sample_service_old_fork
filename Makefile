SERVICE_CAPS = SampleService
SPEC_FILE = SampleService.spec
LIB_DIR = lib
SCRIPTS_DIR = scripts
TEST_DIR = test
TEST_CONFIG_FILE = test.cfg
LBIN_DIR = bin
WORK_DIR = /kb/module/work/tmp
# see https://stackoverflow.com/a/23324703/643675
MAKEFILE_DIR:=$(strip $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST)))))

# Provide TEST_SPEC environment variable when running make test-sdkless to run
# tests in a specific file or directory
TEST_SPEC ?= $(TEST_DIR)

UNIT_TEST_SPEC ?= $(TEST_DIR)/testing/specs/unit
INTEGRATION_TEST_SPEC ?= $(TEST_DIR)/testing/specs/integration
SYSTEM_TEST_SPEC ?= $(TEST_DIR)/testing/specs/system

PYPATH=$(MAKEFILE_DIR)/$(LIB_DIR):$(MAKEFILE_DIR)/$(TEST_DIR)

TEST_PYPATH=$(MAKEFILE_DIR)/$(LIB_DIR):$(MAKEFILE_DIR)/$(TEST_DIR)


TSTFL=$(MAKEFILE_DIR)/$(TEST_DIR)/$(TEST_CONFIG_FILE)
INTEGRATION_TEST_CONFIG=$(MAKEFILE_DIR)/$(TEST_DIR)/testing/specs/integration/$(TEST_CONFIG_FILE)
SYSTEM_TEST_CONFIG=$(MAKEFILE_DIR)/$(TEST_DIR)/testing/specs/system/$(TEST_CONFIG_FILE)
UNIT_TEST_CONFIG=$(MAKEFILE_DIR)/$(TEST_DIR)/testing/specs/unit/$(TEST_CONFIG_FILE)

.PHONY: test

default: compile

all: compile build build-startup-script build-executable-script build-test-script

compile:
# Don't compile server automatically, overwrites fixes to error handling
# Temporarily add the next line to the command line args if recompiliation is needed to add
# methods.
#		--pysrvname $(SERVICE_CAPS).$(SERVICE_CAPS)Server \

	kb-sdk compile $(SPEC_FILE) \
		--out $(LIB_DIR) \
		--pyclname $(SERVICE_CAPS).$(SERVICE_CAPS)Client \
		--dynservver release \
		--pyimplname $(SERVICE_CAPS).$(SERVICE_CAPS)Impl;
	- rm $(LIB_DIR)/$(SERVICE_CAPS)Server.py

	kb-sdk compile $(SPEC_FILE) \
		--out . \
		--html \

test:
	echo Use test-sdkless

validate-types-src:
	echo "Running type validation in 'lib' (mypy)"
	MYPYPATH=$(MAKEFILE_DIR)/$(LIB_DIR) mypy $(LIB_DIR)/$(SERVICE_CAPS)

validate-types-test:
	#MYPYPATH=$(MAKEFILE_DIR)/$(LIB_DIR):$(MAKEFILE_DIR)/$(TEST_DIR) mypy \
	#		--namespace-packages $(LIB_DIR)/$(SERVICE_CAPS)/core $(TEST_DIR)
	echo "Running type validation in 'test' (mypy)"
	echo "WARNING: test type validation disabled"


test-begin:
	coverage erase

test-end:
	@echo "Creating html coverage report"
	coverage html
	@echo "Converting coverage to lcov"
	coverage-lcov --data_file_path .coverage --output_file_path cov_profile.lcov

wait-for-sample-service:
	@echo "Waiting for SampleService to be available"
	@[ "${SAMPLE_SERVICE_URL}" ] || (echo "! Environment variable SAMPLE_SERVICE_URL must be set"; exit 1)
	PYTHONPATH=$(TEST_PYPATH) python -c "from testing.shared.wait_for import wait_for_sample_service; wait_for_sample_service('$(SAMPLE_SERVICE_URL)', 30, 1)"

test-integration:
	@echo "Running integration tests (pytest) in $(INTEGRATION_TEST_SPEC)"
	PYTHONPATH=$(TEST_PYPATH) SAMPLESERV_TEST_FILE=$(INTEGRATION_TEST_CONFIG) \
		pytest --verbose \
		    --cov $(LIB_DIR)/$(SERVICE_CAPS) \
			--cov-append \
			--cov-config=$(TEST_DIR)/coveragerc \
			$(INTEGRATION_TEST_SPEC)

test-system:
	@echo "Running service tests (pytest) in $(SYSTEM_TEST_SPEC)"
	PYTHONPATH=$(TEST_PYPATH) SAMPLESERV_TEST_FILE=$(SYSTEM_TEST_CONFIG) \
		pytest --verbose \
			$(SYSTEM_TEST_SPEC)

test-unit:
	@echo "Running unit tests (pytest) in $(UNIT_TEST_SPEC) with path $(TEST_PYPATH)"
	PYTHONPATH=$(TEST_PYPATH) SAMPLESERV_TEST_FILE=$(UNIT_TEST_CONFIG) \
		pytest --verbose \
			--cov $(LIB_DIR)/$(SERVICE_CAPS) \
			--cov-append \
			--cov-config=$(TEST_DIR)/coveragerc \
			$(UNIT_TEST_SPEC)
	


test-sdkless: validate-types-src validate-types-test test-unit test-integration
	# TODO flake8 and bandit
	# TODO check tests run with kb-sdk test - will need to install mongo and update config
	echo "[test-sdkless] with python path ${PYTHONPATH}"

# to print test output immediately: --capture=tee-sys

#####################
# Run on host
#####################

clean:
	rm -rfv $(LBIN_DIR)

# Managing development and testing container orchestration

start-dev-server:
	sh scripts/start-dev-server.sh

stop-dev-server:
	sh scripts/stop-dev-server.sh

remove-dev-server:
	sh scripts/remove-dev-server.sh

start-test-server:
	sh scripts/start-test-server.sh

stop-test-server:
	sh scripts/stop-test-server.sh

remove-test-server:
	sh scripts/remove-test-server.sh


# Running tests

host-test-begin: 
	@echo "Beginning tests..."
	docker compose -f docker-compose-test.yml run test test-begin

host-test-end: 
	@echo "Ending tests..."
	docker compose -f docker-compose-test.yml run test test-end

host-test-unit: 
	@echo "Running unit tests..."
	docker compose -f docker-compose-test.yml run test test-unit
	docker compose -f docker-compose-test.yml rm -f
	@echo "DONE"

host-tests: host-test-begin host-test-unit host-test-end


#
# docker-compose-test.yml adds the testing container
# docker-compose-test-integration.yml adds support for integrating with the main docker compose services
# Note: MOCK_DATASET_PATH needs to be set 
#
host-test-integration:
	@echo "Running unit tests..."
	docker compose -f docker-compose.yml -f docker-compose-test.yml -f docker-compose-test-integration.yml run test test-integration
	docker compose -f docker-compose.yml -f docker-compose-test.yml -f docker-compose-test-integration.yml stop
	docker compose -f docker-compose.yml -f docker-compose-test.yml -f docker-compose-test-integration.yml rm -f
	@echo "DONE"

host-test-system:
	@echo "Running unit tests..."
	docker compose -f docker-compose.yml -f docker-compose-test.yml -f docker-compose-test-integration.yml run test test-system
	docker compose -f docker-compose.yml -f docker-compose-test.yml -f docker-compose-test-integration.yml stop
	docker compose -f docker-compose.yml -f docker-compose-test.yml -f docker-compose-test-integration.yml rm -f
	@echo "DONE"

# Run in container