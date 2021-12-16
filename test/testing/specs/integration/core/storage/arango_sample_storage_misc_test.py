from testing.shared.common import (
    TEST_COL_DATA_LINK,
    TEST_COL_NODE_EDGE,
    TEST_COL_NODES,
    TEST_COL_SAMPLE,
    TEST_COL_SCHEMA,
    TEST_COL_VER_EDGE,
    TEST_COL_VERSION,
    TEST_COL_WS_OBJ_VER,
)

#
# Testing
#


def test_indexes_created(samplestorage):
    # Shouldn't reach into the internals but only testing
    # Purpose here is to make tests fail if collections are added so devs are reminded to
    # set up any necessary indexes and add index tests
    cols = sorted(
        [
            x["name"]
            for x in samplestorage._db.collections()
            if not x["name"].startswith("_")
        ]
    )

    collections = sorted(
        [
            TEST_COL_SAMPLE,
            TEST_COL_VERSION,
            TEST_COL_VER_EDGE,
            TEST_COL_NODES,
            TEST_COL_NODE_EDGE,
            TEST_COL_DATA_LINK,
            TEST_COL_WS_OBJ_VER,
            TEST_COL_SCHEMA,
        ]
    )

    def assert_index(index, fields):
        assert index["fields"] == fields
        assert index["deduplicate"] is True
        assert index["sparse"] is False
        assert index["type"] == "persistent"
        assert index["unique"] is False

    assert cols == collections

    indexes = samplestorage._col_sample.indexes()
    assert len(indexes) == 1
    assert indexes[0]["fields"] == ["_key"]

    indexes = samplestorage._col_nodes.indexes()
    assert len(indexes) == 3
    assert indexes[0]["fields"] == ["_key"]
    assert_index(indexes[1], ["uuidver"])
    assert_index(indexes[2], ["ver"])

    indexes = samplestorage._col_version.indexes()
    assert len(indexes) == 3
    assert indexes[0]["fields"] == ["_key"]
    assert_index(indexes[1], ["uuidver"])
    assert_index(indexes[2], ["ver"])

    indexes = samplestorage._col_node_edge.indexes()
    assert len(indexes) == 3
    assert indexes[0]["fields"] == ["_key"]
    assert indexes[1]["fields"] == ["_from", "_to"]
    assert_index(indexes[2], ["uuidver"])

    indexes = samplestorage._col_ver_edge.indexes()
    assert len(indexes) == 3
    assert indexes[0]["fields"] == ["_key"]
    assert indexes[1]["fields"] == ["_from", "_to"]
    assert_index(indexes[2], ["uuidver"])

    # Don't add indexes here, Relation engine is responsible for setting up indexes
    # Sample service doesn't use the collection other than verifying it exists
    indexes = samplestorage._col_ws.indexes()
    assert len(indexes) == 1
    assert indexes[0]["fields"] == ["_key"]

    indexes = samplestorage._col_data_link.indexes()
    assert len(indexes) == 6
    assert indexes[0]["fields"] == ["_key"]
    assert indexes[1]["fields"] == ["_from", "_to"]
    assert_index(indexes[2], ["id"])
    assert_index(indexes[3], ["wsid", "objid", "objver"])
    assert_index(indexes[4], ["samuuidver"])
    assert_index(indexes[5], ["sampleid"])

    indexes = samplestorage._col_schema.indexes()
    assert len(indexes) == 1
    assert indexes[0]["fields"] == ["_key"]
