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


def create_test_db(arango_client):
    system_db = arango_client.db("_system")  # default access to _system db
    try:
        system_db.delete_database(TEST_DB_NAME)
    except Exception:
        # we don't care if we had to zap a previous test database
        pass
    system_db.create_database(
        TEST_DB_NAME, [{"username": TEST_USER, "password": TEST_PWD}]
    )
    return arango_client.db(TEST_DB_NAME, TEST_USER, TEST_PWD)


def reset_collections(db):
    drop_collections(db)
    create_collections(db)
    return db


def drop_collections(db):
    print("DROPPING COLLECTIONS")
    try:
        db.delete_collection(TEST_COL_SAMPLE)
        db.delete_collection(TEST_COL_VERSION)
        db.delete_collection(TEST_COL_VER_EDGE)
        db.delete_collection(TEST_COL_NODES)
        db.delete_collection(TEST_COL_NODE_EDGE)
        db.delete_collection(TEST_COL_DATA_LINK)
        db.delete_collection(TEST_COL_WS_OBJ_VER)
        db.delete_collection(TEST_COL_SCHEMA)
    except Exception:
        pass
    return db


def create_collections(db):
    print("CREATING COLLECTIONS")
    db.create_collection(TEST_COL_SAMPLE)
    db.create_collection(TEST_COL_VERSION)
    db.create_collection(TEST_COL_VER_EDGE, edge=True)
    db.create_collection(TEST_COL_NODES)
    db.create_collection(TEST_COL_NODE_EDGE, edge=True)
    db.create_collection(TEST_COL_DATA_LINK, edge=True)
    db.create_collection(TEST_COL_WS_OBJ_VER)
    db.create_collection(TEST_COL_SCHEMA)
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
# We may be able to move some tests
#


@fixture(scope="session")
def temp_dir():
    tempdir = test_utils.get_temp_dir()
    yield tempdir

    if test_utils.get_delete_temp_files():
        remove_all_files(test_utils.get_temp_dir())


@fixture(scope="session")
def kafka_host():
    yield f"{KAFKA_HOST}"


@fixture(scope="session")
def arango():
    client = ArangoClient(hosts=f"{ARANGODB_URL}")
    yield client


@fixture(scope="session")
def workspace_url():
    yield f"{MOCK_SERVICES_URL}/services/ws"


@fixture(scope="session")
def auth_url():
    yield f"{MOCK_SERVICES_URL}/services/auth"


@fixture(scope="session")
def test_db(arango):
    yield create_test_db(arango)


@fixture(scope="function")
def sample_service(test_db):
    db = reset_collections(test_db)
    yield {"url": SAMPLE_SERVICE_URL, "db": db}


@fixture(scope="function")
def sample_service_db(test_db):
    yield reset_collections(test_db)


@fixture(scope="function")
def samplestorage(sample_service_db, arango):
    return samplestorage_method(arango)
