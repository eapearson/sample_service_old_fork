import uuid

from pytest import raises
from SampleService.core.acls import SampleACL
from SampleService.core.errors import (
    ConcurrencyError,
    NoSuchSampleError,
    NoSuchSampleVersionError,
)
from SampleService.core.sample import (
    SampleNode,
    SavedSample,
    SourceMetadata,
    SubSampleType,
)
from SampleService.core.storage.errors import SampleStorageError
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
    TEST_DB_NAME,
    dt,
    make_uuid,
)
from testing.shared.test_utils import assert_exception_correct

TEST_NODE = SampleNode("foo")


#
# Utilities
#


def _save_sample_version_fail(samplestorage, sample, prior_version, expected):
    with raises(Exception) as got:
        samplestorage.save_sample_version(sample, prior_version)
    assert_exception_correct(got.value, expected)


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


def test_save_and_get_sample(samplestorage):
    n1 = SampleNode("root")
    n2 = SampleNode(
        "kid1",
        SubSampleType.TECHNICAL_REPLICATE,
        "root",
        {"a": {"b": "c", "d": "e"}, "f": {"g": "h"}},
        {"m": {"n": "o"}},
        [SourceMetadata("a", "sk", {"a": "b"}), SourceMetadata("f", "sk", {"c": "d"})],
    )
    n3 = SampleNode("kid2", SubSampleType.SUB_SAMPLE, "kid1", {"a": {"b": "c"}})
    n4 = SampleNode(
        "kid3",
        SubSampleType.TECHNICAL_REPLICATE,
        "root",
        user_metadata={"f": {"g": "h"}},
    )

    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")

    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("auser"), [n1, n2, n3, n4], dt(8), "foo")
        )
        is True
    )

    assert samplestorage.get_sample(id_) == SavedSample(
        id_, UserID("auser"), [n1, n2, n3, n4], dt(8), "foo", 1
    )

    assert samplestorage.get_sample_acls(id_) == SampleACL(
        UserID("auser"), dt(8), public_read=False
    )


def test_save_and_get_samples(samplestorage):
    n1 = SampleNode("root")
    n2 = SampleNode(
        "kid1",
        SubSampleType.TECHNICAL_REPLICATE,
        "root",
        {"a": {"b": "c", "d": "e"}, "f": {"g": "h"}},
        {"m": {"n": "o"}},
        [SourceMetadata("a", "sk", {"a": "b"}), SourceMetadata("f", "sk", {"c": "d"})],
    )
    n3 = SampleNode("kid2", SubSampleType.SUB_SAMPLE, "kid1", {"a": {"b": "c"}})
    n4 = SampleNode(
        "kid3",
        SubSampleType.TECHNICAL_REPLICATE,
        "root",
        user_metadata={"f": {"g": "h"}},
    )

    id1_ = uuid.UUID("1234567890abcdef1234567890fbcdef")
    id2_ = uuid.UUID("1234567890abcdef1234567890fbcdea")
    id3_ = uuid.UUID("1234567890abcdef1234567890fbcdeb")

    # save three separate samples
    assert (
        samplestorage.save_sample(
            SavedSample(id1_, UserID("auser"), [n1, n2, n3, n4], dt(8), "foo")
        )
        is True
    )
    assert (
        samplestorage.save_sample(
            SavedSample(id2_, UserID("auser"), [n1, n2, n3], dt(8), "bar")
        )
        is True
    )
    assert (
        samplestorage.save_sample(
            SavedSample(id3_, UserID("auser"), [n1, n2, n4], dt(8), "baz")
        )
        is True
    )

    assert samplestorage.get_samples(
        [
            {"id": id1_, "version": 1},
            {"id": id2_, "version": 1},
            {"id": id3_, "version": 1},
        ]
    ) == [
        SavedSample(id1_, UserID("auser"), [n1, n2, n3, n4], dt(8), "foo", 1),
        SavedSample(id2_, UserID("auser"), [n1, n2, n3], dt(8), "bar", 1),
        SavedSample(id3_, UserID("auser"), [n1, n2, n4], dt(8), "baz", 1),
    ]


def test_save_sample_fail_bad_input(samplestorage):
    with raises(Exception) as got:
        samplestorage.save_sample(None)
    assert_exception_correct(
        got.value, ValueError("sample cannot be a value that evaluates to false")
    )


def test_save_sample_fail_duplicate(samplestorage):
    """
    Tests that saving a sample with the same ID is an error.
    """
    # sample_id = uuid.UUID('1234567890abcdef1234567890abcdef')
    sample_id = uuid.uuid4()
    assert (
        samplestorage.save_sample(
            SavedSample(sample_id, UserID("user1"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    assert (
        samplestorage.save_sample(
            SavedSample(sample_id, UserID("user1"), [TEST_NODE], dt(1), "bar")
        )
        is False
    )


def test_save_sample_fail_duplicate_race_condition(samplestorage):
    """
    The save_sample method is split into two parts; the initial call bails
    early (returning False) if a sample with the same ID exists; the actual
    saving code is a separate method _save_sample_pt2 - so this test simulates
    the "race condition", in which the second call might succeed, since the
    first call might not be complete (e.g. handled in a different worker) when the
    second call starts, and the second call might end up in the second save
    method anyway.
    Note that the original test used the same uuid for the test above and this one,
    but that can cause a false testing error as the first call below could fail
    if the database is not cleaned up first.
    """
    # sample_id = uuid.UUID('1234567890abcdef1234567890abcdef')
    sample_id = uuid.uuid4()
    assert (
        samplestorage.save_sample(
            SavedSample(sample_id, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    # this is a very bad and naughty thing to do
    # not really, protected methods are to prevent accidental mis-use. This is
    # intentional. A real test of this race condition would be quite a bit more
    # complex!
    assert (
        samplestorage._save_sample_pt2(
            SavedSample(sample_id, UserID("user"), [TEST_NODE], dt(1), "bar")
        )
        is False
    )


def test_get_sample_with_non_updated_version_doc(samplestorage):
    # simulates the case where a save failed part way through. The version UUID was added to the
    # sample doc but the node and version doc updates were not completed
    n1 = SampleNode("root")
    n2 = SampleNode("kid1", SubSampleType.TECHNICAL_REPLICATE, "root")
    n3 = SampleNode("kid2", SubSampleType.SUB_SAMPLE, "kid1")
    n4 = SampleNode("kid3", SubSampleType.TECHNICAL_REPLICATE, "root")

    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")

    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("auser"), [n1, n2, n3, n4], dt(1), "foo")
        )
        is True
    )

    # this is very naughty
    # checked that these modifications actually work by viewing the db contents
    samplestorage._col_version.update_match({}, {"ver": -1})
    samplestorage._col_nodes.update_match({"name": "kid2"}, {"ver": -1})

    assert samplestorage.get_sample(id_) == SavedSample(
        id_, UserID("auser"), [n1, n2, n3, n4], dt(1), "foo", 1
    )

    for v in samplestorage._col_version.all():
        assert v["ver"] == 1

    for v in samplestorage._col_nodes.all():
        assert v["ver"] == 1


def test_get_sample_with_non_updated_node_doc(samplestorage):
    # simulates the case where a save failed part way through. The version UUID was added to the
    # sample doc but the node doc updates were not completed
    # the version doc update *must* have been updated for this test to exercise the
    # node checking logic because a non-updated version doc will cause the nodes to be updated
    # immediately.
    n1 = SampleNode("root")
    n2 = SampleNode("kid1", SubSampleType.TECHNICAL_REPLICATE, "root")
    n3 = SampleNode("kid2", SubSampleType.SUB_SAMPLE, "kid1")
    n4 = SampleNode("kid3", SubSampleType.TECHNICAL_REPLICATE, "root")

    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")

    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("auser"), [n1, n2, n3, n4], dt(1), "foo")
        )
        is True
    )

    # this is very naughty
    # checked that these modifications actually work by viewing the db contents
    samplestorage._col_nodes.update_match({"name": "kid1"}, {"ver": -1})

    assert samplestorage.get_sample(id_) == SavedSample(
        id_, UserID("auser"), [n1, n2, n3, n4], dt(1), "foo", 1
    )

    for v in samplestorage._col_nodes.all():
        assert v["ver"] == 1


# TODO: Do we really need backwards compatibility tests? This test was in place
# before samples was released, so all real samples should be compliant.
def test_get_sample_with_missing_source_metadata_key(samplestorage, arango):
    """
    Backwards compatibility test. Checks that a missing smeta key in the sample node returns an
    empty source metadata list.
    """
    sample_id = uuid.uuid4()
    assert (
        samplestorage.save_sample(
            SavedSample(
                sample_id,
                UserID("user"),
                [
                    SampleNode(
                        "mynode",
                        controlled_metadata={"a": {"c": "d"}},
                        source_metadata=[SourceMetadata("a", "b", {"x": "y"})],
                    )
                ],
                dt(7),
                "foo",
            )
        )
        is True
    )

    arango.db(TEST_DB_NAME).aql.execute(
        """
        FOR n in @@col
            FILTER n.name == @name
            UPDATE n WITH {smeta: null} IN @@col
            OPTIONS {keepNull: false}
        """,
        bind_vars={"@col": TEST_COL_NODES, "name": "mynode"},
    )

    cur = arango.db(TEST_DB_NAME).aql.execute(
        """
        FOR n in @@col
            FILTER n.name == @name
            RETURN n
        """,
        bind_vars={"@col": TEST_COL_NODES, "name": "mynode"},
    )
    doc = cur.next()
    del doc["_rev"]
    del doc["_id"]
    del doc["_key"]
    del doc["uuidver"]
    assert doc == {
        "id": str(sample_id),
        "ver": 1,
        "saved": 7000,
        "name": "mynode",
        "type": "BIOLOGICAL_REPLICATE",
        "parent": None,
        "index": 0,
        "cmeta": [{"k": "c", "ok": "a", "v": "d"}],
        "ucmeta": [],
    }

    assert samplestorage.get_sample(sample_id) == SavedSample(
        sample_id,
        UserID("user"),
        [SampleNode("mynode", controlled_metadata={"a": {"c": "d"}})],
        dt(7),
        "foo",
        1,
    )


def test_get_sample_fail_bad_input(samplestorage):
    with raises(Exception) as got:
        samplestorage.get_sample(None)
    assert_exception_correct(
        got.value, ValueError("id_ cannot be a value that evaluates to false")
    )


def test_get_sample_fail_no_sample(samplestorage):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    with raises(Exception) as got:
        samplestorage.get_sample(uuid.UUID("1234567890abcdef1234567890abcdea"))
    assert_exception_correct(
        got.value, NoSuchSampleError("12345678-90ab-cdef-1234-567890abcdea")
    )


def test_get_sample_fail_no_such_version(samplestorage):
    sample_id = make_uuid()
    assert (
        samplestorage.save_sample(
            SavedSample(sample_id, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    with raises(Exception) as got:
        samplestorage.get_sample(sample_id, version=2)
    assert_exception_correct(
        got.value, NoSuchSampleVersionError(f"{str(sample_id)} ver 2")
    )

    assert (
        samplestorage.save_sample_version(
            SavedSample(sample_id, UserID("user2"), [TEST_NODE], dt(1), "bar")
        )
        == 2
    )

    assert samplestorage.get_sample(sample_id) == SavedSample(
        sample_id, UserID("user2"), [TEST_NODE], dt(1), "bar", 2
    )

    with raises(Exception) as got:
        samplestorage.get_sample(sample_id, version=3)
    assert_exception_correct(
        got.value, NoSuchSampleVersionError(f"{str(sample_id)} ver 3")
    )


def test_get_sample_fail_no_version_doc_1_version(samplestorage):
    # This should be impossible in practice unless someone actively deletes records from the db.
    sample_id = make_uuid()
    assert (
        samplestorage.save_sample(
            SavedSample(sample_id, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    # this is very naughty
    verdoc_filters = {"id": str(sample_id), "ver": 1}
    verdoc = samplestorage._col_version.find(verdoc_filters).next()
    samplestorage._col_version.delete_match(verdoc_filters)

    with raises(Exception) as got:
        samplestorage.get_sample(sample_id, version=1)
    assert_exception_correct(
        got.value,
        SampleStorageError(
            f'Corrupt DB: Missing version {verdoc["uuidver"]} '
            + f"for sample {str(sample_id)}"
        ),
    )


def test_get_sample_fail_no_version_doc_2_versions(samplestorage):
    # This should be impossible in practice unless someone actively deletes records from the db.
    sample_id = make_uuid()
    assert (
        samplestorage.save_sample(
            SavedSample(sample_id, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )
    assert (
        samplestorage.save_sample_version(
            SavedSample(sample_id, UserID("user"), [TEST_NODE], dt(1), "bar")
        )
        == 2
    )

    # this is very naughty
    verdoc_filters = {"id": str(sample_id), "ver": 2}
    verdoc = samplestorage._col_version.find(verdoc_filters).next()
    samplestorage._col_version.delete_match(verdoc_filters)

    assert samplestorage.get_sample(sample_id, version=1) == SavedSample(
        sample_id, UserID("user"), [TEST_NODE], dt(1), "foo", 1
    )

    with raises(Exception) as got:
        samplestorage.get_sample(sample_id, version=2)
    assert_exception_correct(
        got.value,
        SampleStorageError(
            f'Corrupt DB: Missing version {verdoc["uuidver"]} '
            + f"for sample {str(sample_id)}"
        ),
    )


def test_get_sample_fail_no_node_docs_1_version(samplestorage):
    # This should be impossible in practice unless someone actively deletes records from the db.
    sample_id = make_uuid()
    assert (
        samplestorage.save_sample(
            SavedSample(sample_id, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    # this is very naughty
    nodedoc_filters = {"id": str(sample_id), "ver": 1}
    nodedoc = samplestorage._col_nodes.find(nodedoc_filters).next()
    samplestorage._col_nodes.delete_match(nodedoc_filters)

    with raises(Exception) as got:
        samplestorage.get_sample(sample_id, version=1)
    assert_exception_correct(
        got.value,
        SampleStorageError(
            (
                "Corrupt DB: "
                f'Missing nodes for version {nodedoc["uuidver"]} of '
                f"sample {str(sample_id)}"
            )
        ),
    )


def test_get_sample_fail_no_node_docs_2_versions(samplestorage):
    # This should be impossible in practice unless someone actively deletes records from the db.
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )
    assert (
        samplestorage.save_sample_version(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "bar")
        )
        == 2
    )

    # this is very naughty
    nodedoc_filters = {"id": "12345678-90ab-cdef-1234-567890abcdef", "ver": 2}
    nodedoc = samplestorage._col_nodes.find(nodedoc_filters).next()
    samplestorage._col_nodes.delete_match(nodedoc_filters)

    assert samplestorage.get_sample(id_, version=1) == SavedSample(
        id_, UserID("user"), [TEST_NODE], dt(1), "foo", 1
    )

    with raises(Exception) as got:
        samplestorage.get_sample(
            uuid.UUID("1234567890abcdef1234567890abcdef"), version=2
        )
    assert_exception_correct(
        got.value,
        SampleStorageError(
            f'Corrupt DB: Missing nodes for version {nodedoc["uuidver"]} of sample '
            + "12345678-90ab-cdef-1234-567890abcdef"
        ),
    )


def test_save_and_get_sample_version(samplestorage):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(42), "foo")
        )
        is True
    )

    n1 = SampleNode("root")
    n2 = SampleNode(
        "kid1",
        SubSampleType.TECHNICAL_REPLICATE,
        "root",
        {"a": {"b": "c", "d": "e"}, "f": {"g": "h"}},
        {"m": {"n": "o"}},
    )
    n3 = SampleNode("kid2", SubSampleType.SUB_SAMPLE, "kid1", {"a": {"b": "c"}})
    n4 = SampleNode(
        "kid3",
        SubSampleType.TECHNICAL_REPLICATE,
        "root",
        user_metadata={"f": {"g": "h"}},
    )

    assert (
        samplestorage.save_sample_version(
            SavedSample(id_, UserID("user2"), [n1, n2, n3, n4], dt(86), "bar")
        )
        == 2
    )
    assert (
        samplestorage.save_sample_version(
            SavedSample(id_, UserID("user3"), [n1], dt(7), "whiz", version=6)
        )
        == 3
    )

    assert samplestorage.get_sample(id_, version=1) == SavedSample(
        id_, UserID("user"), [TEST_NODE], dt(42), "foo", 1
    )

    assert samplestorage.get_sample(id_, version=2) == SavedSample(
        id_, UserID("user2"), [n1, n2, n3, n4], dt(86), "bar", 2
    )

    expected = SavedSample(id_, UserID("user3"), [n1], dt(7), "whiz", 3)
    assert samplestorage.get_sample(id_) == expected
    assert samplestorage.get_sample(id_, version=3) == expected


def test_save_sample_version_fail_bad_input(samplestorage):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    s = SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")

    _save_sample_version_fail(
        samplestorage,
        None,
        None,
        ValueError("sample cannot be a value that evaluates to false"),
    )
    _save_sample_version_fail(
        samplestorage, s, 0, ValueError("prior_version must be > 0")
    )


def test_save_sample_version_fail_no_sample(samplestorage):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    id2 = uuid.UUID("1234567890abcdef1234567890abcdea")
    with raises(Exception) as got:
        samplestorage.save_sample_version(
            SavedSample(id2, UserID("user"), [TEST_NODE], dt(1), "whiz")
        )
    assert_exception_correct(
        got.value, NoSuchSampleError("12345678-90ab-cdef-1234-567890abcdea")
    )


def test_save_sample_version_fail_prior_version(samplestorage):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )
    assert (
        samplestorage.save_sample_version(
            SavedSample(id_, UserID("user"), [SampleNode("bat")], dt(1), "bar")
        )
        == 2
    )

    with raises(Exception) as got:
        samplestorage.save_sample_version(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "whiz"),
            prior_version=1,
        )
    assert_exception_correct(
        got.value,
        ConcurrencyError(
            "Version required for sample "
            + "12345678-90ab-cdef-1234-567890abcdef is 1, but current version is 2"
        ),
    )

    # this is naughty, but need to check race condition
    with raises(Exception) as got:
        samplestorage._save_sample_version_pt2(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "whiz"), 1
        )
    assert_exception_correct(
        got.value,
        ConcurrencyError(
            "Version required for sample "
            + "12345678-90ab-cdef-1234-567890abcdef is 1, but current version is 2"
        ),
    )


def test_sample_version_update(samplestorage):
    # tests that the versions on node and version documents are updated correctly
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [SampleNode("baz")], dt(1), "foo")
        )
        is True
    )

    assert (
        samplestorage.save_sample_version(
            SavedSample(id_, UserID("user"), [SampleNode("bat")], dt(1), "bar")
        )
        == 2
    )

    assert samplestorage.get_sample(id_, version=1) == SavedSample(
        id_, UserID("user"), [SampleNode("baz")], dt(1), "foo", 1
    )

    assert samplestorage.get_sample(id_) == SavedSample(
        id_, UserID("user"), [SampleNode("bat")], dt(1), "bar", 2
    )

    idstr = "12345678-90ab-cdef-1234-567890abcdef"
    vers = set()
    # this is naughty
    for n in samplestorage._col_version.find({"id": idstr}):
        vers.add((n["name"], n["ver"]))
    assert vers == {("foo", 1), ("bar", 2)}

    nodes = set()
    # this is naughty
    for n in samplestorage._col_nodes.find({"id": idstr}):
        nodes.add((n["name"], n["ver"]))
    assert nodes == {("baz", 1), ("bat", 2)}
