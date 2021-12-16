#!/bin/bash

echo '[ENTRYPOINT-TESTING] starting'
echo "[ENTRYPOINT-TESTING] using option ${1}"

script_dir=$(dirname "$(readlink -f "$0")")
export PYTHONPATH=$script_dir/../lib:$PATH:$PYTHONPATH

echo "[ENTRYPOINT-TESTING] Python path: ${PYTHONPATH}"

if [ "${1}" = "bash" ] ; then
  export PYTHONPATH="$script_dir/../test:$PYTHONPATH"
  echo "[ENTRYPOINT-TESTING] shell mode with Python path: ${PYTHONPATH}"
  bash
elif [ "${1}" = "test-begin" ] ; then
  # Python path must include the test directory in order for the test validators
  # to be loadable.
  export PYTHONPATH="$script_dir/../test:$PYTHONPATH"
  echo "[ENTRYPOINT-TESTING] begin tests"
  make test-begin
elif [ "${1}" = "test-end" ] ; then
  # Python path must include the test directory in order for the test validators
  # to be loadable.
  export PYTHONPATH="$script_dir/../test:$PYTHONPATH"
  echo "[ENTRYPOINT-TESTING] end tests"
  make test-end
elif [ "${1}" = "test-unit" ] ; then
  # Python path must include the test directory in order for the test validators
  # to be loadable.
  export PYTHONPATH="$script_dir/../test:$PYTHONPATH"
  echo "[ENTRYPOINT-TESTING] unit-test mode with Python path: ${PYTHONPATH}"
  make test-unit
elif [ "${1}" = "test-integration" ] ; then
  # Python path must include the test directory in order for the test validators
  # to be loadable.
  export PYTHONPATH="$script_dir/../test:$PYTHONPATH"
  echo "[ENTRYPOINT-TESTING] unit-test mode with Python path: ${PYTHONPATH}"
  SAMPLE_SERVICE_URL=http://sampleservice:5000 make wait-for-sample-service
  make test-integration
elif [ "${1}" = "test-system" ] ; then
  # Python path must include the test directory in order for the test validators
  # to be loadable.
  export PYTHONPATH="$script_dir/../test:$PYTHONPATH"
  echo "[ENTRYPOINT-TESTING] unit-test mode with Python path: ${PYTHONPATH}"
  SAMPLE_SERVICE_URL=http://sampleservice:5000 make wait-for-sample-service
  make test-system
else
  echo "[ENTRYPOINT-TESTING] Error! Unknown entrypoint option: ${1}"
  exit 1
fi
