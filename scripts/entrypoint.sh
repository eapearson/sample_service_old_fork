#!/bin/bash

echo '[ENTRYPOINT] starting'

# Create deploy.cfg
if [ ! -z "$CONFIG_URL" ] ; then
    EXTRA=" -env ${CONFIG_URL} -env-header /run/secrets/auth_data"
fi
dockerize ${EXTRA} -template deploy.cfg.tmpl:deploy.cfg

echo "[ENTRYPOINT] using option ${1}"

script_dir=$(dirname "$(readlink -f "$0")")
export KB_DEPLOYMENT_CONFIG=$script_dir/../deploy.cfg
export PYTHONPATH=$script_dir/../lib:$PATH:$PYTHONPATH


echo "[ENTRYPOINT] Python path: ${PYTHONPATH}"

if [ "${1}" = "bash" ] ; then
  export PYTHONPATH="$script_dir/../test:$PYTHONPATH"
  echo "[ENTRYPOINT] shell mode with Python path: ${PYTHONPATH}"
  bash
elif [ "${1}" = "wait" ] ; then
  export PYTHONPATH="$script_dir/../test:$PYTHONPATH"
  echo "[ENTRYPOINT] wait mode with Python path: ${PYTHONPATH}"
  while sleep 3600; do :; done
else
  if [ $# -eq 0 ] ; then
    workers=17
    log_level=info
  elif [ "${1}" = "develop" ] ; then
    # Prepare a test database, so that we have a working database
    # for local development
    python "${script_dir}/../lib/cli/prepare-arango.py"
    workers=1
    log_level=debugr
 
  elif [ "${1}" = "test" ] ; then
    # Python path must include the test directory in order for the test validators
    # to be loadable.
    export PYTHONPATH="$script_dir/../test:$PYTHONPATH"
    echo "[ENTRYPOINT] test mode with Python path: ${PYTHONPATH}"
    python "${script_dir}/../lib/cli/prepare-arango.py"
    workers=1
    log_level=info
  else
    echo "Unknown entrypoint option: ${1}"
    exit 1
  fi

  echo "[ENTRYPOINT] Starting gunicorn with Python path: ${PYTHONPATH}"
  gunicorn --worker-class gevent \
      --timeout 30 \
      --reload \
      --workers $workers \
      --bind :5000 \
      --log-level $log_level  \
      --capture-output \
      SampleService.SampleServiceServer:application
fi
