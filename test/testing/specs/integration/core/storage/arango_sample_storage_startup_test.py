import datetime
import uuid

from pytest import raises
from SampleService.core.errors import MissingParameterError
from SampleService.core.sample import SampleNode, SavedSample, SubSampleType
from SampleService.core.storage.arango_sample_storage import ArangoSampleStorage
from SampleService.core.storage.errors import StorageInitError
from SampleService.core.user import UserID
from testing.shared.common import (
    TEST_COL_DATA_LINK,
    TEST_COL_NODE_EDGE,
    TEST_COL_NODES,
    TEST_COL_SAMPLE,
    TEST_COL_SCHEMA,
    TEST_COL_VER_EDGE,
    TEST_COL_VERSION,
    TEST_COL_WS_OBJ_VER,
    dt,
    nw,
)
from testing.shared.test_utils import assert_exception_correct

TEST_NODE = SampleNode("foo")


#
# Utilities
#


def assert_init_error(
    db,
    colsample,
    colver,
    colveredge,
    colnode,
    colnodeedge,
    colws,
    coldatalink,
    colschema,
    now,
    expected_exception,
):
    with raises(Exception) as got:
        ArangoSampleStorage(
            db,
            colsample,
            colver,
            colveredge,
            colnode,
            colnodeedge,
            colws,
            coldatalink,
            colschema,
            now=now,
        )
    assert_exception_correct(got.value, expected_exception)


#
# Testing
#


def test_startup_and_check_config_doc(samplestorage):
    # this is very naughty
    assert samplestorage._col_schema.count() == 1
    cfgdoc = samplestorage._col_schema.find({}).next()
    assert cfgdoc["_key"] == "schema"
    assert cfgdoc["schemaver"] == 1
    assert cfgdoc["inupdate"] is False

    # check startup works with cfg object in place
    # this is also very naughty
    ss = ArangoSampleStorage(
        samplestorage._db,
        samplestorage._col_sample.name,
        samplestorage._col_version.name,
        samplestorage._col_ver_edge.name,
        samplestorage._col_nodes.name,
        samplestorage._col_node_edge.name,
        samplestorage._col_ws.name,
        samplestorage._col_data_link.name,
        samplestorage._col_schema.name,
    )

    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    n = SampleNode("rootyroot")
    assert ss.save_sample(SavedSample(id_, UserID("u"), [n], dt(1), "foo")) is True
    assert ss.get_sample(id_) == SavedSample(
        id_, UserID("u"), [n], dt(1), "foo", version=1
    )


def test_startup_with_extra_config_doc(sample_service):
    scol = sample_service["db"].collection(TEST_COL_SCHEMA)
    scol.insert_many(
        [
            {"_key": "schema", "schemaver": 1, "inupdate": False},
            {"schema": "schema", "schemaver": 2, "inupdate": False},
        ]
    )

    s = TEST_COL_SAMPLE
    v = TEST_COL_VERSION
    ve = TEST_COL_VER_EDGE
    n = TEST_COL_NODES
    ne = TEST_COL_NODE_EDGE
    ws = TEST_COL_WS_OBJ_VER
    dl = TEST_COL_DATA_LINK
    sc = TEST_COL_SCHEMA

    assert_init_error(
        sample_service["db"],
        s,
        v,
        ve,
        n,
        ne,
        ws,
        dl,
        sc,
        nw,
        StorageInitError(
            (
                "Multiple config objects found in the database. "
                "This should not happen, something is very wrong."
            )
        ),
    )


def test_startup_with_bad_schema_version(sample_service):
    col = sample_service["db"].collection(TEST_COL_SCHEMA)
    col.insert({"_key": "schema", "schemaver": 4, "inupdate": False})

    s = TEST_COL_SAMPLE
    v = TEST_COL_VERSION
    ve = TEST_COL_VER_EDGE
    n = TEST_COL_NODES
    ne = TEST_COL_NODE_EDGE
    ws = TEST_COL_WS_OBJ_VER
    dl = TEST_COL_DATA_LINK
    sc = TEST_COL_SCHEMA

    assert_init_error(
        sample_service["db"],
        s,
        v,
        ve,
        n,
        ne,
        ws,
        dl,
        sc,
        nw,
        StorageInitError("Incompatible database schema. Server is v1, DB is v4"),
    )


def test_startup_in_update(sample_service):
    col = sample_service["db"].collection(TEST_COL_SCHEMA)
    col.insert({"_key": "schema", "schemaver": 1, "inupdate": True})

    s = TEST_COL_SAMPLE
    v = TEST_COL_VERSION
    ve = TEST_COL_VER_EDGE
    n = TEST_COL_NODES
    ne = TEST_COL_NODE_EDGE
    ws = TEST_COL_WS_OBJ_VER
    dl = TEST_COL_DATA_LINK
    sc = TEST_COL_SCHEMA

    assert_init_error(
        sample_service["db"],
        s,
        v,
        ve,
        n,
        ne,
        ws,
        dl,
        sc,
        nw,
        StorageInitError(
            "The database is in the middle of an update from v1 of the schema. Aborting startup."
        ),
    )


def test_startup_with_unupdated_version_and_node_docs(samplestorage):
    # this test simulates a server coming up after a dirty shutdown, where version and
    # node doc integer versions have not been updated
    n1 = SampleNode("root")
    n2 = SampleNode("kid1", SubSampleType.TECHNICAL_REPLICATE, "root")
    n3 = SampleNode("kid2", SubSampleType.SUB_SAMPLE, "kid1")
    n4 = SampleNode("kid3", SubSampleType.TECHNICAL_REPLICATE, "root")

    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")

    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [n1, n2, n3, n4], dt(1), "foo")
        )
        is True
    )

    # this is very naughty
    # checked that these modifications actually work by viewing the db contents
    samplestorage._col_version.update_match({}, {"ver": -1})
    samplestorage._col_nodes.update_match({"name": "kid2"}, {"ver": -1})

    # this is also very naughty
    ArangoSampleStorage(
        samplestorage._db,
        samplestorage._col_sample.name,
        samplestorage._col_version.name,
        samplestorage._col_ver_edge.name,
        samplestorage._col_nodes.name,
        samplestorage._col_node_edge.name,
        samplestorage._col_ws.name,
        samplestorage._col_data_link.name,
        samplestorage._col_schema.name,
    )

    assert samplestorage._col_version.count() == 1
    assert samplestorage._col_ver_edge.count() == 1
    assert samplestorage._col_nodes.count() == 4
    assert samplestorage._col_node_edge.count() == 4

    for v in samplestorage._col_version.all():
        assert v["ver"] == 1

    for v in samplestorage._col_nodes.all():
        assert v["ver"] == 1


def test_startup_with_unupdated_node_docs(samplestorage):
    # this test simulates a server coming up after a dirty shutdown, where
    # node doc integer versions have not been updated
    # version doc cannot be modified such that ver = -1 or the version check will also correct the
    # node docs, negating the point of this test
    n1 = SampleNode("root")
    n2 = SampleNode("kid1", SubSampleType.TECHNICAL_REPLICATE, "root")
    n3 = SampleNode("kid2", SubSampleType.SUB_SAMPLE, "kid1")
    n4 = SampleNode("kid3", SubSampleType.TECHNICAL_REPLICATE, "root")

    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")

    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("u"), [n1, n2, n3, n4], dt(1), "foo")
        )
        is True
    )

    assert (
        samplestorage.save_sample_version(
            SavedSample(id_, UserID("u"), [n1, n2, n3, n4], dt(1), "bar")
        )
        == 2
    )

    # this is very naughty
    sample = samplestorage._col_sample.find({}).next()
    uuidver2 = sample["vers"][1]

    # checked that these modifications actually work by viewing the db contents
    samplestorage._col_nodes.update_match(
        {"uuidver": uuidver2, "name": "kid2"}, {"ver": -1}
    )

    # this is also very naughty
    ArangoSampleStorage(
        samplestorage._db,
        samplestorage._col_sample.name,
        samplestorage._col_version.name,
        samplestorage._col_ver_edge.name,
        samplestorage._col_nodes.name,
        samplestorage._col_node_edge.name,
        samplestorage._col_ws.name,
        samplestorage._col_data_link.name,
        samplestorage._col_schema.name,
    )

    assert samplestorage._col_version.count() == 2
    assert samplestorage._col_ver_edge.count() == 2
    assert samplestorage._col_nodes.count() == 8
    assert samplestorage._col_node_edge.count() == 8

    for v in samplestorage._col_version.all():
        assert v["ver"] == 2 if v["uuidver"] == uuidver2 else 1

    for v in samplestorage._col_nodes.all():
        assert v["ver"] == 2 if v["uuidver"] == uuidver2 else 1


def test_startup_with_no_sample_doc(samplestorage):
    # this test simulates a server coming up after a dirty shutdown, where version and
    # node docs were saved but the sample document was not while saving the first version of
    # a sample
    n1 = SampleNode("root")
    n2 = SampleNode("kid1", SubSampleType.TECHNICAL_REPLICATE, "root")
    n3 = SampleNode("kid2", SubSampleType.SUB_SAMPLE, "kid1")
    n4 = SampleNode("kid3", SubSampleType.TECHNICAL_REPLICATE, "root")

    id1 = uuid.UUID("1234567890abcdef1234567890abcdef")
    id2 = uuid.UUID("1234567890abcdef1234567890abcdea")

    assert (
        samplestorage.save_sample(
            SavedSample(id1, UserID("u"), [n1, n2, n3, n4], dt(1), "foo")
        )
        is True
    )

    assert (
        samplestorage.save_sample(
            SavedSample(id2, UserID("u"), [n1, n2, n3, n4], dt(1000), "foo")
        )
        is True
    )

    # this is very naughty
    assert samplestorage._col_version.count() == 2
    assert samplestorage._col_ver_edge.count() == 2
    assert samplestorage._col_nodes.count() == 8
    assert samplestorage._col_node_edge.count() == 8

    samplestorage._col_sample.delete({"_key": str(id2)})
    # if the sample document hasn't been saved, then none of the integer versions for the
    # sample can have been updated to 1
    samplestorage._col_version.update_match({"id": str(id2)}, {"ver": -1})
    samplestorage._col_nodes.update_match({"id": str(id2)}, {"ver": -1})

    # first test that bringing up the server before the 1hr deletion time limit doesn't change the
    # db:
    # this is also very naughty
    ArangoSampleStorage(
        samplestorage._db,
        samplestorage._col_sample.name,
        samplestorage._col_version.name,
        samplestorage._col_ver_edge.name,
        samplestorage._col_nodes.name,
        samplestorage._col_node_edge.name,
        samplestorage._col_ws.name,
        samplestorage._col_data_link.name,
        samplestorage._col_schema.name,
        now=lambda: datetime.datetime.fromtimestamp(4600, tz=datetime.timezone.utc),
    )

    assert samplestorage._col_version.count() == 2
    assert samplestorage._col_ver_edge.count() == 2
    assert samplestorage._col_nodes.count() == 8
    assert samplestorage._col_node_edge.count() == 8

    # now test that bringing up the server after the limit deletes the docs:
    ArangoSampleStorage(
        samplestorage._db,
        samplestorage._col_sample.name,
        samplestorage._col_version.name,
        samplestorage._col_ver_edge.name,
        samplestorage._col_nodes.name,
        samplestorage._col_node_edge.name,
        samplestorage._col_ws.name,
        samplestorage._col_data_link.name,
        samplestorage._col_schema.name,
        now=lambda: datetime.datetime.fromtimestamp(4601, tz=datetime.timezone.utc),
    )

    assert samplestorage._col_sample.count() == 1
    assert samplestorage._col_version.count() == 1
    assert samplestorage._col_ver_edge.count() == 1
    assert samplestorage._col_nodes.count() == 4
    assert samplestorage._col_node_edge.count() == 4

    sample = samplestorage._col_sample.find({}).next()
    assert sample["id"] == str(id1)
    uuidver = sample["vers"][0]

    assert len(list(samplestorage._col_version.find({"uuidver": uuidver}))) == 1
    assert len(list(samplestorage._col_ver_edge.find({"uuidver": uuidver}))) == 1
    assert len(list(samplestorage._col_nodes.find({"uuidver": uuidver}))) == 4
    assert len(list(samplestorage._col_node_edge.find({"uuidver": uuidver}))) == 4


def test_startup_with_no_version_in_sample_doc(samplestorage):
    # this test simulates a server coming up after a dirty shutdown, where version and
    # node docs were saved but the sample document was not updated while saving the second
    # version of # a sample
    n1 = SampleNode("root")
    n2 = SampleNode("kid1", SubSampleType.TECHNICAL_REPLICATE, "root")
    n3 = SampleNode("kid2", SubSampleType.SUB_SAMPLE, "kid1")
    n4 = SampleNode("kid3", SubSampleType.TECHNICAL_REPLICATE, "root")

    id1 = uuid.UUID("1234567890abcdef1234567890abcdef")

    assert (
        samplestorage.save_sample(
            SavedSample(id1, UserID("u"), [n1, n2, n3, n4], dt(1), "foo")
        )
        is True
    )

    assert (
        samplestorage.save_sample_version(
            SavedSample(id1, UserID("u"), [n1, n2, n3, n4], dt(2000), "foo")
        )
        == 2
    )

    # this is very naughty
    assert samplestorage._col_sample.count() == 1
    assert samplestorage._col_version.count() == 2
    assert samplestorage._col_ver_edge.count() == 2
    assert samplestorage._col_nodes.count() == 8
    assert samplestorage._col_node_edge.count() == 8

    sample = samplestorage._col_sample.find({}).next()
    samplestorage._col_sample.update_match({}, {"vers": sample["vers"][:1]})
    uuidver2 = sample["vers"][1]

    # if the sample document hasn't been updated, then none of the integer versions for the
    # sample can have been updated to 1
    samplestorage._col_version.update_match({"uuidver": uuidver2}, {"ver": -1})
    samplestorage._col_nodes.update_match({"uuidver": uuidver2}, {"ver": -1})

    # first test that bringing up the server before the 1hr deletion time limit doesn't change the
    # db:
    # this is also very naughty
    ArangoSampleStorage(
        samplestorage._db,
        samplestorage._col_sample.name,
        samplestorage._col_version.name,
        samplestorage._col_ver_edge.name,
        samplestorage._col_nodes.name,
        samplestorage._col_node_edge.name,
        samplestorage._col_ws.name,
        samplestorage._col_data_link.name,
        samplestorage._col_schema.name,
        now=lambda: datetime.datetime.fromtimestamp(5600, tz=datetime.timezone.utc),
    )

    assert samplestorage._col_version.count() == 2
    assert samplestorage._col_ver_edge.count() == 2
    assert samplestorage._col_nodes.count() == 8
    assert samplestorage._col_node_edge.count() == 8

    # now test that bringing up the server after the limit deletes the docs:
    ArangoSampleStorage(
        samplestorage._db,
        samplestorage._col_sample.name,
        samplestorage._col_version.name,
        samplestorage._col_ver_edge.name,
        samplestorage._col_nodes.name,
        samplestorage._col_node_edge.name,
        samplestorage._col_ws.name,
        samplestorage._col_data_link.name,
        samplestorage._col_schema.name,
        now=lambda: datetime.datetime.fromtimestamp(5601, tz=datetime.timezone.utc),
    )

    assert samplestorage._col_version.count() == 1
    assert samplestorage._col_ver_edge.count() == 1
    assert samplestorage._col_nodes.count() == 4
    assert samplestorage._col_node_edge.count() == 4

    uuidver1 = sample["vers"][0]

    assert len(list(samplestorage._col_version.find({"uuidver": uuidver1}))) == 1
    assert len(list(samplestorage._col_ver_edge.find({"uuidver": uuidver1}))) == 1
    assert len(list(samplestorage._col_nodes.find({"uuidver": uuidver1}))) == 4
    assert len(list(samplestorage._col_node_edge.find({"uuidver": uuidver1}))) == 4


def test_fail_startup_missing_args(sample_service):
    s = TEST_COL_SAMPLE
    v = TEST_COL_VERSION
    ve = TEST_COL_VER_EDGE
    n = TEST_COL_NODES
    ne = TEST_COL_NODE_EDGE
    ws = TEST_COL_WS_OBJ_VER
    dl = TEST_COL_DATA_LINK
    sc = TEST_COL_SCHEMA

    def assert_error(
        colsample,
        colver,
        colveredge,
        colnode,
        colnodeedge,
        colws,
        coldatalink,
        colschema,
        now,
        expected,
    ):
        assert_init_error(
            sample_service["db"],
            colsample,
            colver,
            colveredge,
            colnode,
            colnodeedge,
            colws,
            coldatalink,
            colschema,
            now,
            MissingParameterError(expected),
        )

    assert_error("", v, ve, n, ne, ws, dl, sc, nw, "sample_collection")
    assert_error(s, "", ve, n, ne, ws, dl, sc, nw, "version_collection")
    assert_error(s, v, "", n, ne, ws, dl, sc, nw, "version_edge_collection")
    assert_error(s, v, ve, "", ne, ws, dl, sc, nw, "node_collection")
    assert_error(s, v, ve, n, "", ws, dl, sc, nw, "node_edge_collection")
    assert_error(
        s, v, ve, n, ne, "", dl, sc, nw, "workspace_object_version_shadow_collection"
    )
    assert_error(s, v, ve, n, ne, ws, "", sc, nw, "data_link_collection")
    assert_error(s, v, ve, n, ne, ws, dl, "", nw, "schema_collection")


def test_fail_startup_invalid_args(sample_service):
    s = TEST_COL_SAMPLE
    v = TEST_COL_VERSION
    ve = TEST_COL_VER_EDGE
    n = TEST_COL_NODES
    ne = TEST_COL_NODE_EDGE
    ws = TEST_COL_WS_OBJ_VER
    dl = TEST_COL_DATA_LINK
    sc = TEST_COL_SCHEMA

    def assert_error(
        db,
        colsample,
        colver,
        colveredge,
        colnode,
        colnodeedge,
        colws,
        coldatalink,
        colschema,
        now,
        expected,
    ):
        assert_init_error(
            db,
            colsample,
            colver,
            colveredge,
            colnode,
            colnodeedge,
            colws,
            coldatalink,
            colschema,
            now,
            ValueError(expected),
        )

    assert_error(
        None,
        s,
        v,
        ve,
        n,
        ne,
        ws,
        dl,
        sc,
        nw,
        "db cannot be a value that evaluates to false",
    )
    assert_error(
        sample_service["db"],
        s,
        v,
        ve,
        n,
        ne,
        ws,
        dl,
        sc,
        None,
        "now cannot be a value that evaluates to false",
    )


def test_fail_startup_incorrect_collection_type(sample_service):
    sample_service["db"].create_collection("sampleedge", edge=True)

    s = TEST_COL_SAMPLE
    v = TEST_COL_VERSION
    ve = TEST_COL_VER_EDGE
    n = TEST_COL_NODES
    ne = TEST_COL_NODE_EDGE
    ws = TEST_COL_WS_OBJ_VER
    dl = TEST_COL_DATA_LINK
    sc = TEST_COL_SCHEMA

    def assert_error(
        colsample,
        colver,
        colveredge,
        colnode,
        colnodeedge,
        colws,
        coldatalink,
        colschema,
        now,
        expected,
    ):
        assert_init_error(
            sample_service["db"],
            colsample,
            colver,
            colveredge,
            colnode,
            colnodeedge,
            colws,
            coldatalink,
            colschema,
            now,
            StorageInitError(expected),
        )

    assert_error(
        "sampleedge",
        v,
        ve,
        n,
        ne,
        ws,
        dl,
        sc,
        nw,
        "sample collection sampleedge is not a vertex collection",
    )
    assert_error(
        s,
        ve,
        ve,
        n,
        ne,
        ws,
        dl,
        sc,
        nw,
        f"version collection {TEST_COL_VER_EDGE} is not a vertex collection",
    )
    assert_error(
        s,
        v,
        v,
        n,
        ne,
        ws,
        dl,
        sc,
        nw,
        f"version edge collection {TEST_COL_VERSION} is not an edge collection",
    )
    assert_error(
        s,
        v,
        ve,
        ne,
        ne,
        ws,
        dl,
        sc,
        nw,
        f"node collection {TEST_COL_NODE_EDGE} is not a vertex collection",
    )
    assert_error(
        s,
        v,
        ve,
        n,
        n,
        ws,
        dl,
        sc,
        nw,
        f"node edge collection {TEST_COL_NODES} is not an edge collection",
    )
    assert_error(
        s,
        v,
        ve,
        n,
        ne,
        dl,
        dl,
        sc,
        nw,
        (
            f"workspace object version shadow collection {TEST_COL_DATA_LINK} "
            "is not a vertex collection"
        ),
    )
    assert_error(
        s,
        v,
        ve,
        n,
        ne,
        ws,
        ws,
        sc,
        nw,
        f"data link collection {TEST_COL_WS_OBJ_VER} is not an edge collection",
    )
    assert_error(
        s,
        v,
        ve,
        n,
        ne,
        ws,
        dl,
        ne,
        nw,
        f"schema collection {TEST_COL_NODE_EDGE} is not a vertex collection",
    )
