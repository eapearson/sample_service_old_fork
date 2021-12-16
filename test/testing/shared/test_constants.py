# Database configuration

# Old Test Config
# TEST_DB_NAME = 'test_db'
# TEST_COL_SAMPLE = 'samples_sample'
# TEST_COL_VERSION = 'samples_version'
# TEST_COL_VER_EDGE = 'samples_ver_edge'
# TEST_COL_NODES = 'samples_nodes'
# TEST_COL_NODE_EDGE = 'samples_nodes_edge'
# TEST_COL_WS_OBJ_VER = 'ws_object_version'
# TEST_COL_DATA_LINK = 'samples_data_link'
# TEST_COL_SCHEMA = 'samples_schema'
# TEST_USER = 'test'
# TEST_PWD = 'test123'

# Um, why not use the actual config?
TEST_DB_NAME = "test_db"
TEST_USER = "test"
TEST_PWD = "test123"

TEST_COL_SAMPLE = "samples_sample"
TEST_COL_VERSION = "samples_version"
TEST_COL_VER_EDGE = "samples_ver_edge"
TEST_COL_NODES = "samples_nodes"
TEST_COL_NODE_EDGE = "samples_nodes_edge"
TEST_COL_DATA_LINK = "samples_data_link"
TEST_COL_WS_OBJ_VER = "ws_object_version"
TEST_COL_SCHEMA = "samples_schema"

# Sample service config

# TODO: Get all hosts from the configuration?

SERVICE_PORT = 5000
SAMPLE_SERVICE_URL = "http://sampleservice:5000"

# Other services configuration

# Arango
ARANGODB_PORT = 8529
ARANGODB_URL = "http://arangodb:8529"

# Kafka
KAFKA_TOPIC = "sampleservice"
KAFKA_TOPIC = "sampleservice"
KAFKA_PORT = 9092
KAFKA_HOST = "kafka:9092"

# Mock Services
MOCK_SERVICES_PORT = 3333
MOCK_SERVICES_URL = "http://mockservices:3333"

# Test data - move to test data file

USER_WS_READ_ADMIN = "wsreadadmin"
TOKEN_WS_READ_ADMIN = "WSREADADMINTOKENXXXXXXXXXXXXXXXX"
USER_WS_FULL_ADMIN = "wsfulladmin"
TOKEN_WS_FULL_ADMIN = "WSFULLADMINTOKENXXXXXXXXXXXXXXXX"
WS_READ_ADMIN = "WS_READ_ADMIN"
WS_FULL_ADMIN = "WS_FULL_ADMIN"

USER_SERVICE = "serviceuser"
TOKEN_SERVICE = "SERVICETOKENXXXXXXXXXXXXXXXXXXXX"

USER1 = "user1"
TOKEN1 = "USER1TOKENXXXXXXXXXXXXXXXXXXXXXX"
USER2 = "user2"
TOKEN2 = "USER2TOKENXXXXXXXXXXXXXXXXXXXXXX"
USER3 = "user3"
TOKEN3 = "USER3TOKENXXXXXXXXXXXXXXXXXXXXXX"
USER4 = "user4"
TOKEN4 = "USER4TOKENXXXXXXXXXXXXXXXXXXXXXX"
USER5 = "user5"
TOKEN5 = "USER5TOKENXXXXXXXXXXXXXXXXXXXXXX"
USER6 = "user6"
TOKEN6 = "USER6TOKENXXXXXXXXXXXXXXXXXXXXXX"

USER_NO_TOKEN1 = "usernt1"
USER_NO_TOKEN2 = "usernt2"
USER_NO_TOKEN3 = "usernt3"
