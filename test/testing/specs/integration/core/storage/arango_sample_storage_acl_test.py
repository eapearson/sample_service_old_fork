import datetime
import uuid

from pytest import raises
from SampleService.core.acls import SampleACL, SampleACLDelta
from SampleService.core.data_link import DataLink
from SampleService.core.errors import NoSuchSampleError, UnauthorizedError
from SampleService.core.sample import (
    SampleAddress,
    SampleNode,
    SampleNodeAddress,
    SavedSample,
)
from SampleService.core.storage.errors import OwnerChangedError
from SampleService.core.user import UserID
from SampleService.core.workspace import UPA, DataUnitID
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


def _update_sample_acls(samplestorage, at_least):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    samplestorage.update_sample_acls(
        id_,
        SampleACLDelta(
            [UserID("foo"), UserID("bar1")],
            [UserID("baz1"), UserID("bat")],
            [UserID("whoo1")],
            public_read=True,
            at_least=at_least,
        ),
        dt(101),
    )

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(101),
        [UserID("foo"), UserID("bar1")],
        [UserID("baz1"), UserID("bat")],
        [UserID("whoo1")],
        True,
    )


def _update_sample_acls_noop(samplestorage, at_least):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    samplestorage.replace_sample_acls(
        id_,
        SampleACL(
            UserID("user"),
            dt(56),
            [UserID("foo"), UserID("bar")],
            [UserID("baz"), UserID("bat")],
            [UserID("whoo")],
            True,
        ),
    )

    samplestorage.update_sample_acls(
        id_,
        SampleACLDelta(
            [UserID("foo")],
            [UserID("bat")],
            [UserID("whoo")],
            [UserID("nouser"), UserID("nouser2")],
            public_read=True,
            at_least=at_least,
        ),
        dt(103),
    )

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(56),
        [UserID("foo"), UserID("bar")],
        [UserID("baz"), UserID("bat")],
        [UserID("whoo")],
        True,
    )


def _update_sample_acls_with_owner_in_acl(samplestorage, admin, write, read):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    samplestorage.update_sample_acls(
        id_,
        SampleACLDelta(admin, write, read, public_read=True, at_least=True),
        dt(101),
    )

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(101),
        [UserID("foo"), UserID("bar1")],
        [UserID("baz1"), UserID("bat")],
        [UserID("whoo1")],
        True,
    )


def _expire_and_get_data_link_via_duid(samplestorage, expired, dataid, expectedmd5):
    sid = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(sid, UserID("user"), [SampleNode("mynode")], dt(1), "foo")
        )
        is True
    )

    lid = uuid.UUID("1234567890abcdef1234567890abcde1")
    samplestorage.create_data_link(
        DataLink(
            lid,
            DataUnitID(UPA("1/1/1"), dataid),
            SampleNodeAddress(SampleAddress(sid, 1), "mynode"),
            dt(-100),
            UserID("userb"),
        )
    )

    # this is naughty
    verdoc1 = samplestorage._col_version.find({"id": str(sid), "ver": 1}).next()
    nodedoc1 = samplestorage._col_nodes.find({"name": "mynode"}).next()

    assert samplestorage.expire_data_link(
        dt(expired), UserID("yay"), duid=DataUnitID(UPA("1/1/1"), dataid)
    ) == DataLink(
        lid,
        DataUnitID(UPA("1/1/1"), dataid),
        SampleNodeAddress(SampleAddress(sid, 1), "mynode"),
        dt(-100),
        UserID("userb"),
        dt(expired),
        UserID("yay"),
    )

    assert samplestorage._col_data_link.count() == 1

    link = samplestorage._col_data_link.get(f"1_1_1_{expectedmd5}-100.0")
    assert link == {
        "_key": f"1_1_1_{expectedmd5}-100.0",
        "_id": f"{TEST_COL_DATA_LINK}/1_1_1_{expectedmd5}-100.0",
        "_from": f"{TEST_COL_WS_OBJ_VER}/1:1:1",
        "_to": nodedoc1["_id"],
        "_rev": link["_rev"],  # no need to test this
        "id": "12345678-90ab-cdef-1234-567890abcde1",
        "wsid": 1,
        "objid": 1,
        "objver": 1,
        "dataid": dataid,
        "sampleid": "12345678-90ab-cdef-1234-567890abcdef",
        "samuuidver": verdoc1["uuidver"],
        "samintver": 1,
        "node": "mynode",
        "created": -100000,
        "createby": "userb",
        "expired": expired * 1000,
        "expireby": "yay",
    }

    assert samplestorage.get_data_link(lid) == DataLink(
        lid,
        DataUnitID(UPA("1/1/1"), dataid),
        SampleNodeAddress(SampleAddress(sid, 1), "mynode"),
        dt(-100),
        UserID("userb"),
        dt(expired),
        UserID("yay"),
    )


def _update_sample_acls_with_false_public(samplestorage, at_least):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    samplestorage.replace_sample_acls(
        id_,
        SampleACL(
            UserID("user"),
            dt(56),
            [UserID("foo"), UserID("bar")],
            [UserID("baz"), UserID("bat")],
            [UserID("whoo")],
            True,
        ),
    )

    samplestorage.update_sample_acls(
        id_, SampleACLDelta(public_read=False, at_least=at_least), dt(89)
    )

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(89),
        [UserID("bar"), UserID("foo")],
        [UserID("baz"), UserID("bat")],
        [UserID("whoo")],
        False,
    )


def _update_sample_acls_with_remove_and_null_public(samplestorage, at_least):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    samplestorage.replace_sample_acls(
        id_,
        SampleACL(
            UserID("user"),
            dt(56),
            [UserID("foo"), UserID("bar")],
            [UserID("baz"), UserID("bat")],
            [UserID("whoo")],
            True,
        ),
    )

    samplestorage.update_sample_acls(
        id_,
        SampleACLDelta(
            [UserID("admin")],
            [UserID("write"), UserID("write2")],
            [UserID("read")],
            [UserID("foo"), UserID("bat"), UserID("whoo"), UserID("notauser")],
            at_least=at_least,
        ),
        dt(102),
    )

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(102),
        [UserID("bar"), UserID("admin")],
        [UserID("baz"), UserID("write"), UserID("write2")],
        [UserID("read")],
        True,
    )


def _update_sample_acls_fail(samplestorage, id_, update, update_time, expected):
    with raises(Exception) as got:
        samplestorage.update_sample_acls(id_, update, update_time)
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


def test_get_sample_acls_with_missing_public_read_key(samplestorage, arango):
    """
    Backwards compatibility test. Checks that a missing pubread key in the ACLs is registered as
    false, and that then changing pubread to True works normally.
    """
    sample_id = make_uuid()
    assert (
        samplestorage.save_sample(
            SavedSample(sample_id, UserID("user"), [SampleNode("mynode")], dt(1), "foo")
        )
        is True
    )

    arango.db(TEST_DB_NAME).aql.execute(
        """
        FOR s in @@col
            FILTER s.id == @id
            UPDATE s WITH {acls: {pubread: null}} IN @@col
            OPTIONS {keepNull: false}
        """,
        bind_vars={"@col": TEST_COL_SAMPLE, "id": str(sample_id)},
    )

    cur = arango.db(TEST_DB_NAME).aql.execute(
        """
        FOR s in @@col
            FILTER s.id == @id
            RETURN s
        """,
        bind_vars={"@col": TEST_COL_SAMPLE, "id": str(sample_id)},
    )
    assert cur.next()["acls"] == {"owner": "user", "admin": [], "write": [], "read": []}

    assert samplestorage.get_sample_acls(sample_id) == SampleACL(UserID("user"), dt(1))

    samplestorage.replace_sample_acls(
        sample_id, SampleACL(UserID("user"), dt(3), public_read=True)
    )

    assert samplestorage.get_sample_acls(sample_id) == SampleACL(
        UserID("user"), dt(3), public_read=True
    )


def test_get_sample_acls_fail_bad_input(samplestorage):
    with raises(Exception) as got:
        samplestorage.get_sample_acls(None)
    assert_exception_correct(
        got.value, ValueError("id_ cannot be a value that evaluates to false")
    )


def test_get_sample_acls_fail_no_sample(samplestorage):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    with raises(Exception) as got:
        samplestorage.get_sample_acls(uuid.UUID("1234567890abcdef1234567890abcdea"))
    assert_exception_correct(
        got.value, NoSuchSampleError("12345678-90ab-cdef-1234-567890abcdea")
    )


def test_replace_sample_acls(samplestorage):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    samplestorage.replace_sample_acls(
        id_,
        SampleACL(
            UserID("user"),
            dt(56),
            [UserID("foo"), UserID("bar")],
            [UserID("baz"), UserID("bat")],
            [UserID("whoo")],
            True,
        ),
    )

    assert samplestorage.get_sample_acls(id_) == SampleACL(
        UserID("user"),
        dt(56),
        [UserID("foo"), UserID("bar")],
        [UserID("baz"), UserID("bat")],
        [UserID("whoo")],
        True,
    )

    samplestorage.replace_sample_acls(
        id_, SampleACL(UserID("user"), dt(83), write=[UserID("baz")])
    )

    assert samplestorage.get_sample_acls(id_) == SampleACL(
        UserID("user"), dt(83), write=[UserID("baz")]
    )


def test_replace_sample_acls_fail_bad_args(samplestorage):
    with raises(Exception) as got:
        samplestorage.replace_sample_acls(None, SampleACL(UserID("user"), dt(1)))
    assert_exception_correct(
        got.value, ValueError("id_ cannot be a value that evaluates to false")
    )

    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    with raises(Exception) as got:
        samplestorage.replace_sample_acls(id_, None)
    assert_exception_correct(
        got.value, ValueError("acls cannot be a value that evaluates to false")
    )


def test_replace_sample_acls_fail_no_sample(samplestorage):
    id1 = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id1, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    id2 = uuid.UUID("1234567890abcdef1234567890abcdea")

    with raises(Exception) as got:
        samplestorage.replace_sample_acls(id2, SampleACL(UserID("user"), dt(1)))
    assert_exception_correct(got.value, NoSuchSampleError(str(id2)))


def test_replace_sample_acls_fail_owner_changed(samplestorage):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    # this is naughty
    samplestorage._db.aql.execute(
        """
        FOR s IN @@col
            UPDATE s WITH {acls: MERGE(s.acls, @acls)} IN @@col
            RETURN s
        """,
        bind_vars={"@col": TEST_COL_SAMPLE, "acls": {"owner": "user2"}},
    )

    with raises(Exception) as got:
        samplestorage.replace_sample_acls(
            id_, SampleACL(UserID("user"), dt(1), write=[UserID("foo")])
        )
    assert_exception_correct(got.value, OwnerChangedError())


def test_update_sample_acls_with_at_least_False(samplestorage):
    # at_least shouldn't change the results of the test, as none of the users are already in ACLs.
    _update_sample_acls(samplestorage, False)


def test_update_sample_acls_with_at_least_True(samplestorage):
    # at_least shouldn't change the results of the test, as none of the users are already in ACLs.
    _update_sample_acls(samplestorage, True)


def test_update_sample_acls_with_at_least_True_and_owner_in_admin_acl(samplestorage):
    # owner should be included in any changes with at_least = True.
    _update_sample_acls_with_owner_in_acl(
        samplestorage,
        [UserID("foo"), UserID("bar1"), UserID("user")],
        [UserID("baz1"), UserID("bat")],
        [UserID("whoo1")],
    )


def test_update_sample_acls_with_at_least_True_and_owner_in_write_acl(samplestorage):
    # owner should be included in any changes with at_least = True.
    _update_sample_acls_with_owner_in_acl(
        samplestorage,
        [UserID("foo"), UserID("bar1")],
        [UserID("baz1"), UserID("bat"), UserID("user")],
        [UserID("whoo1")],
    )


def test_update_sample_acls_with_at_least_True_and_owner_in_read_acl(samplestorage):
    # owner should be included in any changes with at_least = True.
    _update_sample_acls_with_owner_in_acl(
        samplestorage,
        [UserID("foo"), UserID("bar1")],
        [UserID("baz1"), UserID("bat")],
        [UserID("whoo1"), UserID("user")],
    )


def test_update_sample_acls_noop_with_at_least_False(samplestorage):
    _update_sample_acls_noop(samplestorage, False)


def test_update_sample_acls_noop_with_at_least_True(samplestorage):
    _update_sample_acls_noop(samplestorage, True)


def test_update_sample_acls_with_remove_and_null_public_and_at_least_False(
    samplestorage,
):
    _update_sample_acls_with_remove_and_null_public(samplestorage, False)


def test_update_sample_acls_with_remove_and_null_public_and_at_least_True(
    samplestorage,
):
    _update_sample_acls_with_remove_and_null_public(samplestorage, True)


def test_update_sample_acls_with_False_public_and_at_least_False(samplestorage):
    _update_sample_acls_with_false_public(samplestorage, False)


def test_update_sample_acls_with_False_public_and_at_least_True(samplestorage):
    _update_sample_acls_with_false_public(samplestorage, True)


def test_update_sample_acls_with_existing_users(samplestorage):
    """
    Tests that when a user is added to an acl it's removed from any other acls.
    """
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    samplestorage.replace_sample_acls(
        id_,
        SampleACL(
            UserID("user"),
            dt(56),
            admin=[UserID("a1"), UserID("a2"), UserID("arem")],
            write=[UserID("w1"), UserID("w2"), UserID("wrem")],
            read=[UserID("r1"), UserID("r2"), UserID("rrem")],
        ),
    )

    # move user from write -> admin, remove admin
    samplestorage.update_sample_acls(
        id_, SampleACLDelta(admin=[UserID("w1")], remove=[UserID("arem")]), dt(89)
    )

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(89),
        [UserID("a1"), UserID("a2"), UserID("w1")],
        [UserID("w2"), UserID("wrem")],
        [UserID("r1"), UserID("r2"), UserID("rrem")],
        False,
    )

    # move user from read -> admin
    samplestorage.update_sample_acls(id_, SampleACLDelta(admin=[UserID("r1")]), dt(90))

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(90),
        [UserID("a1"), UserID("a2"), UserID("w1"), UserID("r1")],
        [UserID("w2"), UserID("wrem")],
        [UserID("r2"), UserID("rrem")],
        False,
    )

    # move user from write -> read, remove write
    samplestorage.update_sample_acls(
        id_, SampleACLDelta(read=[UserID("w1")], remove=[UserID("wrem")]), dt(91)
    )

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(91),
        [UserID("a1"), UserID("a2"), UserID("r1")],
        [UserID("w2")],
        [UserID("r2"), UserID("w1"), UserID("rrem")],
        False,
    )

    # move user from admin -> read
    samplestorage.update_sample_acls(id_, SampleACLDelta(read=[UserID("a1")]), dt(92))

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(92),
        [UserID("a2"), UserID("r1")],
        [UserID("w2")],
        [UserID("r2"), UserID("w1"), UserID("a1"), UserID("rrem")],
        False,
    )

    # move user from admin -> write, remove read
    samplestorage.update_sample_acls(
        id_, SampleACLDelta(write=[UserID("a2")], remove=[UserID("rrem")]), dt(93)
    )

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(93),
        [UserID("r1")],
        [UserID("w2"), UserID("a2")],
        [UserID("r2"), UserID("w1"), UserID("a1")],
        False,
    )

    # move user from read -> write, move user from write -> read, noop on read user
    samplestorage.update_sample_acls(
        id_,
        SampleACLDelta(write=[UserID("r2")], read=[UserID("a2"), UserID("a1")]),
        dt(94),
    )

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(94),
        [UserID("r1")],
        [UserID("w2"), UserID("r2")],
        [UserID("w1"), UserID("a2"), UserID("a1")],
        False,
    )


def test_update_sample_acls_with_existing_users_and_at_least_True(samplestorage):
    """
    Tests that when a user is added to an acl it's state is unchanged if it's already in a
    'better' acl.
    """
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    samplestorage.replace_sample_acls(
        id_,
        SampleACL(
            UserID("user"),
            dt(56),
            admin=[UserID("a1"), UserID("a2"), UserID("arem")],
            write=[UserID("w1"), UserID("w2"), UserID("wrem")],
            read=[UserID("r1"), UserID("r2"), UserID("rrem")],
        ),
    )

    samplestorage.update_sample_acls(
        id_,
        SampleACLDelta(
            admin=[UserID("a1")],  # noop admin->admin
            write=[UserID("a2"), UserID("r1")],  # noop admin->write, read->write
            read=[UserID("r2")],  # noop read->read
            remove=[UserID("arem")],  # remove admin
            at_least=True,
        ),
        dt(89),
    )

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(89),
        [UserID("a1"), UserID("a2")],
        [UserID("w1"), UserID("w2"), UserID("wrem"), UserID("r1")],
        [UserID("r2"), UserID("rrem")],
        False,
    )

    samplestorage.update_sample_acls(
        id_,
        SampleACLDelta(
            admin=[UserID("r1"), UserID("r2")],  # write->admin, read->admin
            write=[UserID("w2")],  # noop write->write
            read=[UserID("a1"), UserID("w1")],  # noop admin->read, noop write->read
            remove=[UserID("rrem"), UserID("wrem")],  # remove read and write
            at_least=True,
            public_read=True,
        ),
        dt(90),
    )

    res = samplestorage.get_sample_acls(id_)
    assert res == SampleACL(
        UserID("user"),
        dt(90),
        [UserID("a1"), UserID("a2"), UserID("r1"), UserID("r2")],
        [UserID("w1"), UserID("w2")],
        [],
        True,
    )


def test_update_sample_acls_fail_bad_args(samplestorage):
    id_ = uuid.uuid4()
    s = SampleACLDelta()
    t = dt(1)

    _update_sample_acls_fail(
        samplestorage,
        None,
        s,
        t,
        ValueError("id_ cannot be a value that evaluates to false"),
    )
    _update_sample_acls_fail(
        samplestorage,
        id_,
        None,
        t,
        ValueError("update cannot be a value that evaluates to false"),
    )
    _update_sample_acls_fail(
        samplestorage,
        id_,
        s,
        None,
        ValueError("update_time cannot be a value that evaluates to false"),
    )
    _update_sample_acls_fail(
        samplestorage,
        id_,
        s,
        datetime.datetime.fromtimestamp(1),
        ValueError("update_time cannot be a naive datetime"),
    )


def test_update_sample_acls_fail_no_sample(samplestorage):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    _update_sample_acls_fail(
        samplestorage,
        uuid.UUID("1234567890abcdef1234567890abcde1"),
        SampleACLDelta(),
        dt(1),
        NoSuchSampleError("12345678-90ab-cdef-1234-567890abcde1"),
    )

    _update_sample_acls_fail(
        samplestorage,
        uuid.UUID("1234567890abcdef1234567890abcde1"),
        SampleACLDelta(at_least=True),
        dt(1),
        NoSuchSampleError("12345678-90ab-cdef-1234-567890abcde1"),
    )


def test_update_sample_acls_fail_alters_owner(samplestorage):
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("us"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    err = UnauthorizedError(
        "ACLs for the sample owner us may not be modified by a delta update."
    )
    t = dt(1)

    _update_sample_acls_fail(samplestorage, id_, SampleACLDelta([UserID("us")]), t, err)
    _update_sample_acls_fail(
        samplestorage, id_, SampleACLDelta(write=[UserID("us")]), t, err
    )
    _update_sample_acls_fail(
        samplestorage, id_, SampleACLDelta(read=[UserID("us")]), t, err
    )
    _update_sample_acls_fail(
        samplestorage, id_, SampleACLDelta(remove=[UserID("us")]), t, err
    )
    _update_sample_acls_fail(
        samplestorage, id_, SampleACLDelta(remove=[UserID("us")], at_least=True), t, err
    )


def test_update_sample_acls_fail_owner_changed(samplestorage):
    """
    This tests a race condition that could occur when the owner of a sample changes after
    the sample ACLs are pulled from Arango to check against the sample delta to ensure the owner
    is not altered by the delta.
    """
    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")
    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("user"), [TEST_NODE], dt(1), "foo")
        )
        is True
    )

    for al in [True, False]:
        with raises(Exception) as got:
            samplestorage._update_sample_acls_pt2(
                id_, SampleACLDelta([UserID("a")], at_least=al), UserID("user2"), dt(1)
            )
        assert_exception_correct(
            got.value,
            OwnerChangedError(
                # we don't really ever expect this to happen, but just in case...
                "The sample owner unexpectedly changed during the operation. Please retry. "
                + "If this error occurs frequently, code changes may be necessary."
            ),
        )
