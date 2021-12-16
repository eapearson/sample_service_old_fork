import os
import shutil

from arango import ArangoClient
from pytest import fixture
from SampleService.core.storage.arango_sample_storage import ArangoSampleStorage
from testing.shared import test_utils
from testing.shared.common import (
    TEST_COL_DATA_LINK,
    TEST_COL_NODE_EDGE,
    TEST_COL_NODES,
    TEST_COL_SAMPLE,
    TEST_COL_SCHEMA,
    TEST_COL_VER_EDGE,
    TEST_COL_VERSION,
    TEST_COL_WS_OBJ_VER,
    TEST_DB_NAME,
    TEST_PWD,
    TEST_USER,
    create_deploy_cfg,
)
from testing.shared.test_constants import (
    ARANGODB_URL,
    KAFKA_HOST,
    MOCK_SERVICES_URL,
    SAMPLE_SERVICE_URL,
)


def delete_test_db(arango_client):
    system_db = arango_client.db("_system")  # default access to _system db
    system_db.delete_database(TEST_DB_NAME)


DB_USED = False


def create_test_db(arango_client):
    system_db = arango_client.db("_system")  # default access to _system db
    system_db.create_database(
        TEST_DB_NAME, [{"username": TEST_USER, "password": TEST_PWD}]
    )
    return arango_client.db(TEST_DB_NAME, TEST_USER, TEST_PWD)


def clear_db_and_recreate(arango_client):
    global DB_USED
    try:
        delete_test_db(arango_client)
    except Exception as e:
        # First time through, there is probably no db to delete, so an error is thrown;
        # just absorb it. But maybe there is (from a remnant of a previous failed test),
        # so we try anyway.
        # TODO: it would be cleaner to check if the db exists first?
        if DB_USED:
            raise e
        else:
            pass

    db = create_test_db(arango_client)
    db.create_collection(TEST_COL_SAMPLE)
    db.create_collection(TEST_COL_VERSION)
    db.create_collection(TEST_COL_VER_EDGE, edge=True)
    db.create_collection(TEST_COL_NODES)
    db.create_collection(TEST_COL_NODE_EDGE, edge=True)
    db.create_collection(TEST_COL_DATA_LINK, edge=True)
    db.create_collection(TEST_COL_WS_OBJ_VER)
    db.create_collection(TEST_COL_SCHEMA)
    DB_USED = True
    return db


def remove_all_files(directory):
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print("Failed to delete %s. Reason: %s" % (file_path, e))


def samplestorage_method(arango):
    return ArangoSampleStorage(
        arango.db(TEST_DB_NAME, TEST_USER, TEST_PWD),
        TEST_COL_SAMPLE,
        TEST_COL_VERSION,
        TEST_COL_VER_EDGE,
        TEST_COL_NODES,
        TEST_COL_NODE_EDGE,
        TEST_COL_WS_OBJ_VER,
        TEST_COL_DATA_LINK,
        TEST_COL_SCHEMA,
    )


#
# Fixtures
#
# Generally, some fixtures can be reset for each test module, others need to
# be clean at the beginning of each test.
#
# This does slow down tests a lot!
#
# We may be able to move some tests
#

#
# Module scope
#


@fixture(scope="module")
def temp_dir():
    tempdir = test_utils.get_temp_dir()
    yield tempdir

    if test_utils.get_delete_temp_files():
        remove_all_files(test_utils.get_temp_dir())


@fixture(scope="module")
def kafka_host():
    yield f"{KAFKA_HOST}"


@fixture(scope="module")
def arango():
    client = ArangoClient(hosts=f"{ARANGODB_URL}")
    yield client


@fixture(scope="module")
def workspace_url():
    yield f"{MOCK_SERVICES_URL}/services/ws"


@fixture(scope="module")
def auth_url():
    yield f"{MOCK_SERVICES_URL}/services/auth"


#
# Function scope
#


def reset_db(arango):
    db = clear_db_and_recreate(arango)
    config_path = create_deploy_cfg()
    os.environ["KB_DEPLOYMENT_CONFIG"] = config_path
    return db


@fixture(scope="function")
def sample_service(arango):
    db = reset_db(arango)
    yield {"url": SAMPLE_SERVICE_URL, "db": db}


@fixture(scope="function")
def sample_service_db(arango):
    yield reset_db(arango)


@fixture(scope="function")
def samplestorage(sample_service_db, arango):
    return samplestorage_method(arango)
