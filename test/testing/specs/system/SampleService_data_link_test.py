# These tests cover the integration of the entire system and do not go into details - that's
# what unit tests are for. As such, typically each method will get a single happy path test and
# a single unhappy path test unless otherwise warranted.

import copy
import datetime
import time
import uuid

from testing.shared.common import (
    assert_create_sample,
    assert_error_create_link,
    assert_error_rpc_call,
    assert_result_create_link,
    assert_result_rpc_call,
    check_kafka_messages,
    clear_kafka_messages,
    create_link,
    create_sample,
    get_current_epochmillis,
    get_sample_node_id,
    make_expected_sample,
    replace_acls,
    rpc_call_result,
)
from testing.shared.service_client import ServiceClient
from testing.shared.test_cases import CASE_01, CASE_02, CASE_04
from testing.shared.test_constants import (
    TOKEN1,
    TOKEN2,
    TOKEN3,
    TOKEN4,
    TOKEN5,
    USER1,
    USER2,
    USER3,
    USER4,
)
from testing.shared.test_utils import assert_ms_epoch_close_to_now

#
# Utils
#


def get_links_from_sample(url, token, params):
    result = rpc_call_result(url, token, "get_data_links_from_sample", [params])
    assert len(result) == 2
    return result


def _expire_data_link(url, dataid, kafka_host):
    """also tests that 'as_user' is ignored if 'as_admin' is false"""
    # Requires
    # Workspace 13 owned by USER3, writable by USER4, one object.
    upa = "13/1/1"

    clear_kafka_messages(kafka_host)

    # create samples
    sample_id = assert_create_sample(url, TOKEN3, CASE_01)

    # USER4 should be an admin of the sample
    replace_acls(url, sample_id, TOKEN3, {"admin": [USER4]})

    # create links

    # The main link of interest, using the passed-in dataid
    link_id1 = create_link(
        url,
        TOKEN3,
        {"id": sample_id, "version": 1, "node": "root", "upa": upa, "dataid": dataid},
        USER3,
    )

    # Another link, to a different dataid
    link_id2 = create_link(
        url,
        TOKEN3,
        {"id": sample_id, "version": 1, "node": "root", "upa": upa, "dataid": "fake"},
        USER3,
    )

    time.sleep(1)  # need to be able to set a reasonable effective time to fetch links

    # expire link
    # USER4 can expire a data link as another user.
    # TODO: that isn't the point of this test, so maybe just remove
    # the as_user. Expiring as another user, is that a normal use case?
    assert_result_rpc_call(
        url,
        TOKEN4,
        "expire_data_link",
        [{"upa": upa, "dataid": dataid, "as_user": USER1}],
        None,
    )

    # check links
    result = rpc_call_result(
        url,
        TOKEN4,
        "get_data_links_from_data",
        [{"upa": upa, "effective_time": get_current_epochmillis() - 500}],
    )

    assert len(result) == 2
    assert_ms_epoch_close_to_now(result["effective_time"])
    links = result["links"]
    assert len(links) == 2
    # TODO: sort this out. current_link and expired_link
    for link in links:
        if link["dataid"] == "fake":
            current_link = link
        else:
            expired_link = link
    assert_ms_epoch_close_to_now(expired_link["expired"])
    assert_ms_epoch_close_to_now(expired_link["created"] + 1000)
    del expired_link["created"]
    del expired_link["expired"]

    assert expired_link == {
        "linkid": link_id1,
        "id": sample_id,
        "version": 1,
        "node": "root",
        "upa": upa,
        "dataid": dataid,
        "createdby": USER3,
        "expiredby": USER4,
    }

    assert_ms_epoch_close_to_now(current_link["created"] + 1000)
    del current_link["created"]

    assert current_link == {
        "linkid": link_id2,
        "id": sample_id,
        "version": 1,
        "node": "root",
        "upa": upa,
        "dataid": "fake",
        "createdby": USER3,
        "expiredby": None,
        "expired": None,
    }
    #
    check_kafka_messages(
        kafka_host,
        [
            {"event_type": "NEW_SAMPLE", "sample_id": sample_id, "sample_ver": 1},
            {"event_type": "ACL_CHANGE", "sample_id": sample_id},
            {"event_type": "NEW_LINK", "link_id": link_id1},
            {"event_type": "NEW_LINK", "link_id": link_id2},
            {"event_type": "EXPIRED_LINK", "link_id": link_id1},
        ],
    )


def _expire_data_link_as_admin(url, sample_expire_user, expected_user, kafka_host):
    # Requires:
    # Users: USER4
    # Workspaces:
    # - X - owned by USER3, writable by USER4, with one object
    upa = "13/1/1"
    sample_creator_token = TOKEN3
    sample_creator_user = USER3
    sample_admin_token = TOKEN2
    sample_reader_user = TOKEN4

    clear_kafka_messages(kafka_host)

    # create samples
    sample_id = assert_create_sample(url, sample_creator_token, CASE_01, 1)

    # create links
    link_id = assert_result_create_link(
        url,
        sample_creator_token,
        {"id": sample_id, "version": 1, "node": "root", "upa": upa, "dataid": "duidy"},
        sample_creator_user,
    )

    time.sleep(1)  # need to be able to set a resonable effective time to fetch links

    # expire link
    assert_result_rpc_call(
        url,
        sample_admin_token,
        "expire_data_link",
        [{"upa": upa, "dataid": "duidy", "as_admin": 1, "as_user": sample_expire_user}],
        None,
    )

    # check links
    result = rpc_call_result(
        url,
        sample_reader_user,
        "get_data_links_from_data",
        [{"upa": upa, "effective_time": get_current_epochmillis() - 500}],
    )

    assert len(result) == 2
    assert_ms_epoch_close_to_now(result["effective_time"])
    links = result["links"]
    assert len(links) == 1
    link = links[0]
    assert_ms_epoch_close_to_now(link["expired"])
    assert_ms_epoch_close_to_now(link["created"] + 1000)
    del link["created"]
    del link["expired"]

    assert link == {
        "linkid": link_id,
        "id": sample_id,
        "version": 1,
        "node": "root",
        "upa": upa,
        "dataid": "duidy",
        "createdby": sample_creator_user,
        "expiredby": expected_user,
    }

    check_kafka_messages(
        kafka_host,
        [
            {"event_type": "NEW_SAMPLE", "sample_id": sample_id, "sample_ver": 1},
            {"event_type": "NEW_LINK", "link_id": link_id},
            {"event_type": "EXPIRED_LINK", "link_id": link_id},
        ],
    )


def _get_links_from_data(url, token, params, debug=False):
    result = rpc_call_result(url, token, "get_data_links_from_data", [params], debug)
    # Do we really need to check this? Yes, it has two keys: links, effective_time.
    assert len(result) == 2
    return result


def assert_create_link(sample_service, TOKEN3, param, USER3):
    pass


#
# Tests
#


def test_create_links_and_get_links_from_sample_basic(sample_service, kafka_host):
    """
    Also tests that the 'as_user' key is ignored if 'as_admin' is falsy.
    """
    clear_kafka_messages(kafka_host)

    # create samples
    sample_id1 = assert_create_sample(sample_service["url"], TOKEN3, CASE_01, 1)

    sample_id2 = assert_create_sample(sample_service["url"], TOKEN4, CASE_02, 1)

    # ver 2
    case02 = copy.deepcopy(CASE_02)
    case02["sample"]["id"] = sample_id2
    assert_create_sample(sample_service["url"], TOKEN4, case02, 2)

    # create links

    # as_user should be ignored unless as_admin is true
    # TODO: the as_user test should probably be a separate standalone
    # test, this test function is quite long enough already!

    # TODO: Umm, this one should not work
    link_id1 = create_link(
        sample_service["url"],
        TOKEN3,
        {
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "3/2/2",
            "as_user": USER1,
        },
        USER3,
    )

    link_id2 = create_link(
        sample_service["url"],
        TOKEN3,
        {
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "3/1/1",
            "dataid": "column1",
        },
        USER3,
    )

    link_id3 = create_link(
        sample_service["url"],
        TOKEN4,
        {
            "id": sample_id2,
            "version": 1,
            "node": "root2",
            "upa": "3/2/1",
            "dataid": "column2",
        },
        USER4,
    )

    # # get links from sample 1

    result = rpc_call_result(
        sample_service["url"],
        TOKEN3,
        "get_data_links_from_sample",
        [{"id": sample_id1, "version": 1}],
    )
    assert_ms_epoch_close_to_now(result["effective_time"])
    links = result["links"]
    expected_links = [
        {
            "linkid": link_id1,
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "3/2/2",
            "dataid": None,
            "createdby": USER3,
            "expiredby": None,
            "expired": None,
        },
        {
            "linkid": link_id2,
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "3/1/1",
            "dataid": "column1",
            "createdby": USER3,
            "expiredby": None,
            "expired": None,
        },
    ]

    assert len(links) == len(expected_links)
    for link in links:
        assert_ms_epoch_close_to_now(link["created"])
        del link["created"]

    for link in expected_links:
        assert link in links

    # get links from sample 2
    result = rpc_call_result(
        sample_service["url"],
        TOKEN4,
        "get_data_links_from_sample",
        [{"id": sample_id2, "version": 1}],
    )

    assert len(result) == 2
    assert_ms_epoch_close_to_now(result["effective_time"])
    links = result["links"]
    assert_ms_epoch_close_to_now(links[0]["created"])
    del links[0]["created"]

    assert links == [
        {
            "linkid": link_id3,
            "id": sample_id2,
            "version": 1,
            "node": "root2",
            "upa": "3/2/1",
            "dataid": "column2",
            "createdby": USER4,
            "expiredby": None,
            "expired": None,
        }
    ]
    #
    # # get links from ver 2 of sample 2
    result = rpc_call_result(
        sample_service["url"],
        TOKEN4,
        "get_data_links_from_sample",
        [{"id": sample_id2, "version": 2}],
    )

    assert len(result) == 2
    assert_ms_epoch_close_to_now(result["effective_time"])
    assert result["links"] == []

    check_kafka_messages(
        kafka_host,
        [
            {"event_type": "NEW_SAMPLE", "sample_id": sample_id1, "sample_ver": 1},
            {"event_type": "NEW_SAMPLE", "sample_id": sample_id2, "sample_ver": 1},
            {"event_type": "NEW_SAMPLE", "sample_id": sample_id2, "sample_ver": 2},
            {"event_type": "NEW_LINK", "link_id": link_id1},
            {"event_type": "NEW_LINK", "link_id": link_id2},
            {"event_type": "NEW_LINK", "link_id": link_id3},
        ],
    )


def test_update_and_get_links_from_sample(sample_service, kafka_host):
    """
    Also tests getting links from a sample using an effective time
    """
    clear_kafka_messages(kafka_host)

    # create samples
    sample_id1 = assert_create_sample(sample_service["url"], TOKEN3, CASE_04, 1)

    replace_acls(sample_service["url"], sample_id1, TOKEN3, {"admin": [USER4]})

    # create links
    link_id1 = create_link(
        sample_service["url"],
        TOKEN3,
        {
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "3/1/1",
            "dataid": "yay",
        },
        USER3,
    )

    oldlinkactive = datetime.datetime.now()
    time.sleep(1)

    # update link node
    link_id2 = create_link(
        sample_service["url"],
        TOKEN4,
        {
            "id": sample_id1,
            "version": 1,
            "node": "subsample",
            "upa": "3/1/1",
            "dataid": "yay",
            "update": 1,
        },
        USER4,
    )

    # get current link
    result = rpc_call_result(
        sample_service["url"],
        TOKEN3,
        "get_data_links_from_sample",
        [{"id": sample_id1, "version": 1}],
    )
    assert len(result) == 2
    assert_ms_epoch_close_to_now(result["effective_time"])
    del result["effective_time"]
    created = result["links"][0]["created"]
    assert_ms_epoch_close_to_now(created, 2000)
    del result["links"][0]["created"]
    assert result == {
        "links": [
            {
                "linkid": link_id2,
                "id": sample_id1,
                "version": 1,
                "node": "subsample",
                "upa": "3/1/1",
                "dataid": "yay",
                "createdby": USER4,
                "expiredby": None,
                "expired": None,
            }
        ]
    }

    # get expired link
    result = rpc_call_result(
        sample_service["url"],
        TOKEN3,
        "get_data_links_from_sample",
        [
            {
                "id": sample_id1,
                "version": 1,
                "effective_time": round(oldlinkactive.timestamp() * 1000),
            }
        ],
    )

    assert result["links"][0]["expired"] == created - 1
    assert_ms_epoch_close_to_now(result["links"][0]["created"] + 1000)
    del result["links"][0]["created"]
    del result["links"][0]["expired"]
    assert result == {
        "effective_time": round(oldlinkactive.timestamp() * 1000),
        "links": [
            {
                "linkid": link_id1,
                "id": sample_id1,
                "version": 1,
                "node": "root",
                "upa": "3/1/1",
                "dataid": "yay",
                "createdby": USER3,
                "expiredby": USER4,
            }
        ],
    }

    check_kafka_messages(
        kafka_host,
        [
            {"event_type": "NEW_SAMPLE", "sample_id": sample_id1, "sample_ver": 1},
            {"event_type": "ACL_CHANGE", "sample_id": sample_id1},
            {"event_type": "NEW_LINK", "link_id": link_id1},
            {"event_type": "NEW_LINK", "link_id": link_id2},
            {"event_type": "EXPIRED_LINK", "link_id": link_id1},
        ],
    )


def test_create_data_link_as_admin(sample_service):
    # create samples
    sample_id1 = create_sample(
        sample_service["url"],
        TOKEN3,
        {
            "name": "mysample",
            "node_tree": [
                {"id": "root", "type": "BioReplicate"},
                {"id": "foo", "type": "TechReplicate", "parent": "root"},
            ],
        },
        1,
    )

    # create links
    link_id1 = create_link(
        sample_service["url"],
        TOKEN2,
        {
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "3/1/1",
            "dataid": "foo",
            "as_admin": 1,
        },
        USER2,
    )

    link_id2 = create_link(
        sample_service["url"],
        TOKEN2,
        {
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "3/1/1",
            "dataid": "bar",
            "as_admin": 1,
            "as_user": f"     {USER4}     ",
        },
        USER4,
    )

    # get link
    result = rpc_call_result(
        sample_service["url"],
        TOKEN3,
        "get_data_links_from_sample",
        [{"id": sample_id1, "version": 1}],
    )

    assert len(result) == 2
    assert_ms_epoch_close_to_now(result["effective_time"])
    links = result["links"]
    expected_links = [
        {
            "linkid": link_id1,
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "3/1/1",
            "dataid": "foo",
            "createdby": USER2,
            "expiredby": None,
            "expired": None,
        },
        {
            "linkid": link_id2,
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "3/1/1",
            "dataid": "bar",
            "createdby": USER4,
            "expiredby": None,
            "expired": None,
        },
    ]

    assert len(links) == len(expected_links)
    for link in links:
        assert_ms_epoch_close_to_now(link["created"])
        del link["created"]

    for link in expected_links:
        assert link in links


def test_get_links_from_sample_exclude_workspaces(sample_service):
    """
    Tests that unreadable workspaces are excluded from link results
    """
    # Requires workspace objects which meet the following:
    # 1. ws 4 - foo; created by user3
    #   - object 1
    # 2. ws 5 - bar; created by user4
    #   - object 1 - bar
    #     - USER3 - read
    # 3. ws 6 - baz; created by user4
    #    - object 1 - bar
    #      - GLOBAL - read
    # 4. ws 7 - bat; crated by user4
    #    - object 1 - bar

    # create sample
    sample_id1 = assert_create_sample(sample_service["url"], TOKEN3, CASE_01)
    replace_acls(sample_service["url"], sample_id1, TOKEN3, {"admin": [USER4]})

    # create links
    link_id1 = create_link(
        sample_service["url"],
        TOKEN3,
        {"id": sample_id1, "version": 1, "node": "root", "upa": "4/1/1"},
        USER3,
    )
    link_id2 = create_link(
        sample_service["url"],
        TOKEN4,
        {"id": sample_id1, "version": 1, "node": "root", "upa": "5/1/1"},
        USER4,
    )
    link_id3 = create_link(
        sample_service["url"],
        TOKEN4,
        {
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "6/1/1",
            "dataid": "whee",
        },
        USER4,
    )

    create_link(
        sample_service["url"],
        TOKEN4,
        {"id": sample_id1, "version": 1, "node": "root", "upa": "7/1/1"},
        USER4,
    )

    # check correct links are returned
    result = get_links_from_sample(
        sample_service["url"], TOKEN3, {"id": sample_id1, "version": 1}
    )

    assert_ms_epoch_close_to_now(result["effective_time"])
    links = result["links"]
    expected_links = [
        {
            "linkid": link_id1,
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "4/1/1",
            "dataid": None,
            "createdby": USER3,
            "expiredby": None,
            "expired": None,
        },
        {
            "linkid": link_id2,
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "5/1/1",
            "dataid": None,
            "createdby": USER4,
            "expiredby": None,
            "expired": None,
        },
        {
            "linkid": link_id3,
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "6/1/1",
            "dataid": "whee",
            "createdby": USER4,
            "expiredby": None,
            "expired": None,
        },
    ]

    assert len(links) == len(expected_links)
    for link in links:
        assert_ms_epoch_close_to_now(link["created"])
        del link["created"]

    for link in expected_links:
        assert link in links

    # test with anon user
    replace_acls(sample_service["url"], sample_id1, TOKEN3, {"public_read": 1})
    result = get_links_from_sample(
        sample_service["url"], None, {"id": sample_id1, "version": 1}
    )

    assert_ms_epoch_close_to_now(result["effective_time"])
    links = result["links"]
    expected_links = [
        {
            "linkid": link_id3,
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": "6/1/1",
            "dataid": "whee",
            "createdby": USER4,
            "expiredby": None,
            "expired": None,
        }
    ]

    assert len(links) == len(expected_links)
    for link in links:
        assert_ms_epoch_close_to_now(link["created"])
        del link["created"]

    for link in expected_links:
        assert link in links


def test_get_links_from_sample_as_admin(sample_service):
    # create sample
    sample_id = assert_create_sample(sample_service["url"], TOKEN4, CASE_01)

    # create links
    # Workspace 7 is not shared with anyone, "created" by user 4.
    link_id = create_link(
        sample_service["url"],
        TOKEN4,
        {"id": sample_id, "version": 1, "node": "root", "upa": "7/1/1"},
        USER4,
    )

    # check correct links are returned, user 3 has read admin perms, but not full
    result = rpc_call_result(
        sample_service["url"],
        TOKEN3,
        "get_data_links_from_sample",
        [{"id": sample_id, "version": 1, "as_admin": 1}],
    )

    assert len(result) == 2
    assert_ms_epoch_close_to_now(result["effective_time"])
    assert len(result["links"]) == 1
    link = result["links"][0]
    assert_ms_epoch_close_to_now(link["created"])
    del link["created"]

    assert link == {
        "linkid": link_id,
        "id": sample_id,
        "version": 1,
        "node": "root",
        "upa": "7/1/1",
        "dataid": None,
        "createdby": USER4,
        "expiredby": None,
        "expired": None,
    }


def test_get_links_from_sample_public_read(sample_service):
    """
    A sample data link from a public sample to a public object
    should be readable by a user without explicit permission to either
    and by an anonymous user (no token).
    """
    # create sample
    sample_id = assert_create_sample(sample_service["url"], TOKEN1, CASE_01)

    # Make sample public
    replace_acls(sample_service["url"], sample_id, TOKEN1, {"public_read": 1})

    # create link to object in publicly readable workspace 8.
    link_id = create_link(
        sample_service["url"],
        TOKEN1,
        {"id": sample_id, "version": 1, "node": "root", "upa": "8/1/1"},
        USER1,
    )

    for token in [None, TOKEN4]:  # anon user & user without explicit permission
        # check correct links are returned
        result = rpc_call_result(
            sample_service["url"],
            token,
            "get_data_links_from_sample",
            [{"id": sample_id, "version": 1}],
        )
        assert len(result) == 2
        assert_ms_epoch_close_to_now(result["effective_time"])
        assert len(result["links"]) == 1
        link = result["links"][0]
        assert_ms_epoch_close_to_now(link["created"])
        del link["created"]

        assert link == {
            "linkid": link_id,
            "id": sample_id,
            "version": 1,
            "node": "root",
            "upa": "8/1/1",
            "dataid": None,
            "createdby": USER1,
            "expiredby": None,
            "expired": None,
        }


def test_create_link_param_fail(sample_service):
    """
    Test parameter validation. Since these tests don't actually touch
    the sample, we don't generate one.
    """
    sample_id = "foo"
    assert_error_create_link(
        sample_service["url"],
        TOKEN3,
        {"version": 1, "node": "root", "upa": "1/1/1", "dataid": "yay"},
        "Sample service error code 30000 Missing input parameter: id",
    )
    assert_error_create_link(
        sample_service["url"],
        TOKEN3,
        {"id": sample_id, "node": "root", "upa": "1/1/1", "dataid": "yay"},
        "Sample service error code 30000 Missing input parameter: version",
    )
    assert_error_create_link(
        sample_service["url"],
        TOKEN3,
        {
            "id": sample_id,
            "version": 1,
            "node": "root",
            "upa": "upalupa",
            "dataid": "yay",
        },
        "Sample service error code 30001 Illegal input parameter: upalupa is not a valid UPA",
    )
    assert_error_create_link(
        sample_service["url"],
        TOKEN3,
        {"id": sample_id, "version": 1, "node": "root", "upa": "100/1/1"},
        "Sample service error code 50040 No such workspace data: No workspace with id 100 exists",
    )


def test_create_link_fail(sample_service):
    # Requires:
    # Workspace 10 - owned by USER3, no objects
    # Workspace 11 - owned by USER3, read for USER4
    # Workspace 12 - owned by USER3, read for USER4, one object

    sample_id = assert_create_sample(sample_service["url"], TOKEN3, CASE_01)

    assert_error_create_link(
        sample_service["url"],
        TOKEN3,
        {"id": sample_id, "version": 1, "node": "root", "upa": "10/1/1"},
        "Sample service error code 50040 No such workspace data: Object 10/1/1 does not exist",
    )

    # Ensure that attempting to create a link by a user without admin permissions
    # on the sample will fail. Note that the workspace is not touched, so the
    # up doesn't really matter.
    for acl in [None, "read", "write"]:
        if acl is None:
            replace_acls(sample_service["url"], sample_id, TOKEN3, {})
        else:
            replace_acls(sample_service["url"], sample_id, TOKEN3, {acl: [USER4]})

        assert_error_create_link(  # fails if permission granted is admin
            sample_service["url"],
            TOKEN4,
            {"id": sample_id, "version": 1, "node": "root", "upa": "DOES NOT MATTER"},
            "Sample service error code 20000 Unauthorized: User user4 cannot "
            + f"administrate sample {sample_id}",
        )

    # Make a user an admin for the sample, and have them try to link to a
    # workspace they can only read from - write is required.
    replace_acls(sample_service["url"], sample_id, TOKEN3, {"admin": [USER4]})
    assert_error_create_link(
        sample_service["url"],
        TOKEN4,
        {"id": sample_id, "version": 1, "node": "root", "upa": "11/1/1"},
        "Sample service error code 20000 Unauthorized: User user4 cannot write to upa 11/1/1",
    )

    # Given a workspace with an object, attempt to link a sample via
    # a node id which does not exist.
    assert_error_create_link(
        sample_service["url"],
        TOKEN3,
        {"id": sample_id, "version": 1, "node": "fake", "upa": "12/1/1"},
        f"Sample service error code 50030 No such sample node: {sample_id} ver 1 fake",
    )


def test_create_link_as_admin_fail(sample_service):
    # Requires:
    # Workspace 12 - owned by USER3, read for USER4, one object

    sample_id = assert_create_sample(sample_service["url"], TOKEN3, CASE_01)

    # USER2 is a sample service admin.

    # Here we use an invalid user name format.
    assert_error_create_link(
        sample_service["url"],
        TOKEN2,
        {
            "id": sample_id,
            "version": 1,
            "node": "root",
            "upa": "12/1/1",
            "as_admin": 1,
            "as_user": "foo\bbar",
        },
        "Sample service error code 30001 Illegal input parameter: "
        + "userid contains control characters",
    )

    # And a username which does not exist (in our mock data set)
    assert_error_create_link(
        sample_service["url"],
        TOKEN2,
        {
            "id": sample_id,
            "version": 1,
            "node": "root",
            "upa": "12/1/1",
            "as_admin": 1,
            "as_user": "fake",
        },
        "Sample service error code 50000 No such user: fake",
    )

    # USER3 is not an admin.
    assert_error_create_link(
        sample_service["url"],
        TOKEN3,
        {
            "id": sample_id,
            "version": 1,
            "node": "root",
            "upa": "12/1/1",
            "as_admin": 1,
            "as_user": USER4,
        },
        "Sample service error code 20000 Unauthorized: User user3 does not have "
        + "the necessary administration privileges to run method create_data_link",
    )


def test_create_link_fail_link_exists(sample_service):
    # Requires:
    # Workspace owned by USER3 with one object.
    sample_id = assert_create_sample(sample_service["url"], TOKEN3, CASE_01)

    # This one should succeed.
    create_link(
        sample_service["url"],
        TOKEN3,
        {
            "id": sample_id,
            "version": 1,
            "node": "root",
            "upa": "12/1/1",
            "dataid": "yay",
        },
        USER3,
    )

    assert_error_create_link(
        sample_service["url"],
        TOKEN3,
        {
            "id": sample_id,
            "version": 1,
            "node": "root",
            "upa": "12/1/1",
            "dataid": "yay",
        },
        "Sample service error code 60000 Data link exists for data ID: 1/1/1:yay",
    )


def test_get_links_from_sample_fail(sample_service):
    sample_id = assert_create_sample(sample_service["url"], TOKEN3, CASE_01)

    def get_link_from_sample_fail(token, params, expected):
        assert_error_rpc_call(
            sample_service["url"],
            token,
            "get_data_links_from_sample",
            [params],
            expected,
        )

    get_link_from_sample_fail(
        TOKEN3, {}, "Sample service error code 30000 Missing input parameter: id"
    )
    get_link_from_sample_fail(
        TOKEN3,
        {"id": sample_id},
        "Sample service error code 30000 Missing input parameter: version",
    )
    get_link_from_sample_fail(
        TOKEN3,
        {"id": sample_id, "version": 1, "effective_time": "foo"},
        (
            "Sample service error code 30001 Illegal input parameter: key 'effective_time' "
            "value of 'foo' is not a valid epoch millisecond timestamp"
        ),
    )
    get_link_from_sample_fail(
        TOKEN4,
        {"id": sample_id, "version": 1},
        f"Sample service error code 20000 Unauthorized: User user4 cannot read sample {sample_id}",
    )
    get_link_from_sample_fail(
        None,
        {"id": sample_id, "version": 1},
        (
            "Sample service error code 20000 Unauthorized: "
            f"Anonymous users cannot read sample {sample_id}"
        ),
    )
    badid = uuid.uuid4()
    get_link_from_sample_fail(
        TOKEN3,
        {"id": str(badid), "version": 1},
        f"Sample service error code 50010 No such sample: {badid}",
    )

    # admin tests
    get_link_from_sample_fail(
        TOKEN4,
        {"id": sample_id, "version": 1, "as_admin": 1},
        "Sample service error code 20000 Unauthorized: User user4 does not have the "
        + "necessary administration privileges to run method get_data_links_from_sample",
    )
    get_link_from_sample_fail(
        None,
        {"id": sample_id, "version": 1, "as_admin": 1},
        "Sample service error code 20000 Unauthorized: Anonymous users "
        + "may not act as service administrators.",
    )


def test_expire_data_link(sample_service, kafka_host):
    _expire_data_link(sample_service["url"], None, kafka_host)


def test_expire_data_link_with_data_id(sample_service, kafka_host):
    _expire_data_link(sample_service["url"], "whee", kafka_host)


def test_expire_data_link_as_admin(sample_service, kafka_host):
    """
    Tests the case of administratively expiring a link without a current user;
    presumably this is the case for automated expirations. In this case, the admin
    user is the one given credit.
    """
    _expire_data_link_as_admin(sample_service["url"], None, USER2, kafka_host)


def test_expire_data_link_as_admin_impersonate_user(sample_service, kafka_host):
    _expire_data_link_as_admin(sample_service["url"], USER4, USER4, kafka_host)


def test_expire_data_link_fail(sample_service):
    # Requires
    # Users:
    # USER3 - owns workspace
    # Workspace
    # 4 - owned by USER3, shared with no-one, one object
    # Z - owned by USER3, shared writable with USER4, one object.
    upa = "4/1/1"
    upa_writable = "13/1/1"
    bad_upa = "4/2/1"
    data_id = "yay"
    bad_data_id = "boo"

    # create samples
    sample_id = assert_create_sample(sample_service["url"], TOKEN3, CASE_01, 1)

    # create a data link

    # This one links to a workspace only writable to USER3
    assert_result_create_link(
        sample_service["url"],
        TOKEN3,
        {"id": sample_id, "version": 1, "node": "root", "upa": upa, "dataid": data_id},
        USER3,
    )

    # This one links to a workspace writable by USER4 as well.
    assert_result_create_link(
        sample_service["url"],
        TOKEN3,
        {
            "id": sample_id,
            "version": 1,
            "node": "root",
            "upa": upa_writable,
            "dataid": data_id,
        },
        USER3,
    )

    def _expire_data_link_fail(token, params, expected_message, debug=False):
        assert_error_rpc_call(
            sample_service["url"],
            token,
            "expire_data_link",
            [params],
            expected_message,
            debug=debug,
        )

    # Failure expiration cases
    _expire_data_link_fail(
        TOKEN3, {}, "Sample service error code 30000 Missing input parameter: upa"
    )

    _expire_data_link_fail(
        TOKEN3,
        {"upa": "1/0/1"},
        "Sample service error code 30001 Illegal input parameter: 1/0/1 is not a valid UPA",
    )

    _expire_data_link_fail(
        TOKEN3,
        {"upa": "1/1/1", "dataid": "foo\nbar"},
        "Sample service error code 30001 Illegal input parameter: "
        + "dataid contains control characters",
    )

    _expire_data_link_fail(
        TOKEN4,
        {"upa": "1/1/1", "dataid": "yay"},
        "Sample service error code 20000 Unauthorized: User user4 cannot write to workspace 1",
    )

    # Use a non-existent workspace
    # TODO: model deleted workspace in mock data
    # _expire_data_link_fail(TOKEN3, {'upa': '1/1/1', 'dataid': 'yay'},
    #                        'Sample service error code 50040 No such workspace data: Workspace 1 is deleted')

    # Attempt to expire a link using an upa which has not been linked
    _expire_data_link_fail(
        TOKEN3,
        {"upa": bad_upa, "dataid": data_id},
        f"Sample service error code 50050 No such data link: {bad_upa}:{data_id}",
    )

    # Attempt to expire a link using a data id that has not been linked.
    bad_data_id = "boo"
    _expire_data_link_fail(
        TOKEN3,
        {"upa": upa, "dataid": bad_data_id},
        f"Sample service error code 50050 No such data link: {upa}:{bad_data_id}",
    )

    # Now use a workspace in which USER4 has write permission, to get past that hurdle,
    # but trigger error because this user does not have admin permission for the sample.
    _expire_data_link_fail(
        TOKEN4,
        {"upa": upa_writable, "dataid": data_id},
        (
            "Sample service error code 20000 Unauthorized: User user4 cannot "
            f"administrate sample {sample_id}"
        ),
    )

    # admin tests

    # Malformed username for as_user
    _expire_data_link_fail(
        TOKEN2,
        {"upa": upa, "dataid": data_id, "as_admin": 1, "as_user": "foo\tbar"},
        "Sample service error code 30001 Illegal input parameter: "
        + "userid contains control characters",
    )

    _expire_data_link_fail(
        TOKEN3,
        {"upa": upa, "dataid": data_id, "as_admin": 1, "as_user": USER4},
        "Sample service error code 20000 Unauthorized: User user3 does not have "
        + "the necessary administration privileges to run method expire_data_link",
    )

    _expire_data_link_fail(
        TOKEN2,
        {"upa": upa, "dataid": data_id, "as_admin": 1, "as_user": "fake"},
        "Sample service error code 50000 No such user: fake",
    )


def test_get_links_from_data(sample_service):
    # Requirements:
    # Users:
    # Workspaces:
    # - X - owned by USER3, shared writable to USER4, 3 objects (necessary?)
    #     - obj 1 -
    #     - obj 2
    #     - obj 2 ver 2
    #
    upa1 = "13/1/1"
    upa2v1 = "13/2/1"
    upa2v2 = "13/2/2"

    # create samples
    sample_id1 = assert_create_sample(sample_service["url"], TOKEN3, CASE_01, 1)
    sample_id2 = assert_create_sample(sample_service["url"], TOKEN4, CASE_01, 1)

    # ver 2
    case01 = copy.deepcopy(CASE_01)
    case01["sample"]["id"] = sample_id2
    assert_create_sample(sample_service["url"], TOKEN4, case01, 2)

    # create links
    # TODO: It isn't clear why we are using different upas in each case.
    link_id1 = assert_result_create_link(
        sample_service["url"],
        TOKEN3,
        {"id": sample_id1, "version": 1, "node": "root", "upa": upa2v2},
        USER3,
    )

    link_id2 = assert_result_create_link(
        sample_service["url"],
        TOKEN4,
        {
            "id": sample_id2,
            "version": 1,
            "node": "root",
            "upa": upa1,
            "dataid": "column1",
        },
        USER4,
    )

    link_id3 = assert_result_create_link(
        sample_service["url"],
        TOKEN4,
        {
            "id": sample_id2,
            "version": 2,
            "node": "root",
            "upa": upa2v2,
            "dataid": "column2",
        },
        USER4,
    )

    # get links from object 1/2/2
    result = _get_links_from_data(sample_service["url"], TOKEN3, {"upa": upa2v2})

    assert_ms_epoch_close_to_now(result["effective_time"])
    links = result["links"]
    expected_links = [
        {
            "linkid": link_id1,
            "id": sample_id1,
            "version": 1,
            "node": "root",
            "upa": upa2v2,
            "dataid": None,
            "createdby": USER3,
            "expiredby": None,
            "expired": None,
        },
        {
            "linkid": link_id3,
            "id": sample_id2,
            "version": 2,
            "node": "root",
            "upa": upa2v2,
            "dataid": "column2",
            "createdby": USER4,
            "expiredby": None,
            "expired": None,
        },
    ]
    #
    assert len(links) == len(expected_links)
    for link in links:
        assert_ms_epoch_close_to_now(link["created"])
        del link["created"]

    for link in expected_links:
        assert link in links

    # get links from object 1
    result = _get_links_from_data(sample_service["url"], TOKEN3, {"upa": upa1})

    assert_ms_epoch_close_to_now(result["effective_time"])
    links = result["links"]
    assert len(links) == 1
    assert_ms_epoch_close_to_now(links[0]["created"])
    del links[0]["created"]
    assert links == [
        {
            "linkid": link_id2,
            "id": sample_id2,
            "version": 1,
            "node": "root",
            "upa": upa1,
            "dataid": "column1",
            "createdby": USER4,
            "expiredby": None,
            "expired": None,
        }
    ]

    # get links from object 2 version 1
    result = _get_links_from_data(sample_service["url"], TOKEN3, {"upa": upa2v1})

    assert_ms_epoch_close_to_now(result["effective_time"])
    assert result["links"] == []


def test_get_links_from_data_expired(sample_service):
    # Requirements:
    # Users:
    # Workspaces:
    # 13 - owned by USER3, shared writable with USER4, 1 object
    upa = "13/1/1"

    # create sample
    sample_id = assert_create_sample(sample_service["url"], TOKEN3, CASE_04)
    replace_acls(sample_service["url"], sample_id, TOKEN3, {"admin": [USER4]})

    # create links
    link_id1 = assert_result_create_link(
        sample_service["url"],
        TOKEN3,
        {"id": sample_id, "version": 1, "node": "root", "upa": upa, "dataid": "yay"},
        USER3,
    )

    oldlinkactive = datetime.datetime.now()
    time.sleep(1)

    # update link node to link to the subsample node
    # NOTE: we don't this pattern!!
    link_id2 = assert_result_create_link(
        sample_service["url"],
        TOKEN4,
        {
            "id": sample_id,
            "version": 1,
            "node": "subsample",
            "upa": upa,
            "dataid": "yay",
            "update": 1,
        },
        USER4,
    )

    # get current link
    result = rpc_call_result(
        sample_service["url"], TOKEN3, "get_data_links_from_data", [{"upa": upa}]
    )

    assert len(result) == 2
    assert_ms_epoch_close_to_now(result["effective_time"])
    del result["effective_time"]
    links = result["links"]
    assert len(links) == 1
    link = links[0]
    created = link["created"]
    assert_ms_epoch_close_to_now(created)
    del link["created"]
    assert links == [
        {
            "linkid": link_id2,
            "id": sample_id,
            "version": 1,
            "node": "subsample",
            "upa": upa,
            "dataid": "yay",
            "createdby": USER4,
            "expiredby": None,
            "expired": None,
        }
    ]

    # get expired link
    effective_time = round(oldlinkactive.timestamp() * 1000)
    result = rpc_call_result(
        sample_service["url"],
        TOKEN3,
        "get_data_links_from_data",
        [{"upa": upa, "effective_time": effective_time}],
    )

    links = result["links"]
    assert len(links) == 1
    link = links[0]
    assert link["expired"] == created - 1
    assert_ms_epoch_close_to_now(link["created"] + 1000)
    del link["created"]
    del link["expired"]
    assert result == {
        "effective_time": effective_time,
        "links": [
            {
                "linkid": link_id1,
                "id": sample_id,
                "version": 1,
                "node": "root",
                "upa": upa,
                "dataid": "yay",
                "createdby": USER3,
                "expiredby": USER4,
            }
        ],
    }


def test_get_links_from_data_public_read(sample_service):
    # Requirements:
    #
    # Users:
    # USER1 owner of the workspace, creator of sample, creator of link
    # USER4 fetcher of data links
    #
    # Workspaces:
    # 8 - owned by USER1, shared read globally, one object
    #
    upa = "8/1/1"
    sample_params = CASE_01
    node_id = sample_params["sample"]["node_tree"][0]["id"]

    # create samples
    sample_id = assert_create_sample(sample_service["url"], TOKEN1, sample_params)

    # create links
    link_id = assert_result_create_link(
        sample_service["url"],
        TOKEN1,
        {"id": sample_id, "version": 1, "node": node_id, "upa": upa},
        USER1,
    )

    for token in [None, TOKEN4]:  # anon user, user 4 has no explicit perms
        result = _get_links_from_data(sample_service["url"], token, {"upa": upa})

        assert_ms_epoch_close_to_now(result["effective_time"])
        assert len(result["links"]) == 1
        link = result["links"][0]
        assert_ms_epoch_close_to_now(link["created"])
        del link["created"]
        assert link == {
            "linkid": link_id,
            "id": sample_id,
            "version": 1,
            "node": node_id,
            "upa": upa,
            "dataid": None,
            "createdby": USER1,
            "expiredby": None,
            "expired": None,
        }


def test_get_links_from_data_as_admin(sample_service):
    # Requirements:
    #
    # Users:
    # USER4 owner of workspace, creator of sample and links,
    # USER3 fetcher of data links
    #
    # Workspaces:
    # 7 - owned by USER4,  one object
    #
    upa = "7/1/1"
    sample_params = CASE_01
    node_id = get_sample_node_id(sample_params)
    token_owner = TOKEN4
    username_owner = USER4
    token_readadmin = TOKEN3

    # create sample
    sample_id = assert_create_sample(
        sample_service["url"], token_owner, sample_params, 1
    )

    # create link
    link_id = assert_result_create_link(
        sample_service["url"],
        token_owner,
        {"id": sample_id, "version": 1, "node": node_id, "upa": upa},
        username_owner,
    )

    # get links from object, user 3 has admin read perms
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=token_readadmin
    )
    result = sample_service_client.call_assert_result(
        "get_data_links_from_data", {"upa": upa, "as_admin": 1}
    )

    assert len(result) == 2
    assert_ms_epoch_close_to_now(result["effective_time"])
    assert len(result["links"]) == 1
    link = result["links"][0]
    assert_ms_epoch_close_to_now(link["created"])
    del link["created"]
    assert link == {
        "linkid": link_id,
        "id": sample_id,
        "version": 1,
        "node": node_id,
        "upa": upa,
        "dataid": None,
        "createdby": username_owner,
        "expiredby": None,
        "expired": None,
    }


def test_get_links_from_data_fail(sample_service):
    # Requirements:
    #
    # Users:
    # USER3 owner of workspace, creator of sample and links,
    # USER3 fetcher of data links
    # USER4 no access
    #
    # Workspaces:
    # 4 - owned by USER3,  one object
    # 10 - owned by USER3, no objects
    token_owner = TOKEN3
    token_unauth = TOKEN4
    username_unauth = USER4
    upa_with_object = "4/1/1"
    upa_no_objects = "10/1/1"
    upa_non_existent_workspace = "100/1/1"
    non_existent_workspace = 100

    def assert_error_get_link_from_data(token, params, expected, debug=False):
        assert_error_rpc_call(
            sample_service["url"],
            token,
            "get_data_links_from_data",
            [params],
            expected,
            debug,
        )

    # Parameter validation errors
    assert_error_get_link_from_data(
        token_owner, {}, "Sample service error code 30000 Missing input parameter: upa"
    )

    assert_error_get_link_from_data(
        token_owner,
        {"upa": upa_with_object, "effective_time": "foo"},
        (
            "Sample service error code 30001 Illegal input parameter: "
            "key 'effective_time' value of 'foo' is not a valid epoch "
            "millisecond timestamp"
        ),
    )

    # Auth errors
    assert_error_get_link_from_data(
        token_unauth,
        {"upa": upa_with_object},
        (
            "Sample service error code 20000 Unauthorized: "
            f"User {username_unauth} cannot read upa {upa_with_object}"
        ),
    )

    assert_error_get_link_from_data(
        None,
        {"upa": upa_with_object},
        (
            "Sample service error code 20000 Unauthorized: "
            f"Anonymous users cannot read upa {upa_with_object}"
        ),
    )

    assert_error_get_link_from_data(
        token_owner,
        {"upa": upa_no_objects},
        (
            "Sample service error code 50040 No such workspace data: "
            f"Object {upa_no_objects} does not exist"
        ),
    )

    # admin tests (also tests missing / deleted objects)
    assert_error_get_link_from_data(
        token_unauth,
        {"upa": upa_with_object, "as_admin": 1},
        (
            "Sample service error code 20000 Unauthorized: "
            f"User {username_unauth} does not have the necessary "
            "administration privileges to run method get_data_links_from_data"
        ),
    )

    assert_error_get_link_from_data(
        None,
        {"upa": upa_with_object, "as_admin": 1},
        (
            "Sample service error code 20000 Unauthorized: "
            "Anonymous users may not act as service administrators."
        ),
    )
    assert_error_get_link_from_data(
        token_owner,
        {"upa": upa_no_objects, "as_admin": 1},
        (
            "Sample service error code 50040 No such workspace data: "
            f"Object {upa_no_objects} does not exist"
        ),
    )
    assert_error_get_link_from_data(
        token_owner,
        {"upa": upa_non_existent_workspace, "as_admin": 1},
        (
            "Sample service error code 50040 No such workspace data: "
            f"No workspace with id {non_existent_workspace} exists"
        ),
    )

    # wscli.delete_objects([{'ref': '1/1'}])
    assert_error_get_link_from_data(
        token_owner,
        {"upa": upa_no_objects, "as_admin": 1},
        (
            "Sample service error code 50040 No such workspace data: "
            f"Object {upa_no_objects} does not exist"
        ),
        debug=False,
    )

    # wscli.delete_workspace({'id': 1})
    # TODO: Add support for workspace deletion
    # _get_link_from_data_fail(
    #     sample_port, TOKEN3, {'upa': '1/1/1', 'as_admin': 1},
    #     'Sample service error code 50040 No such workspace data: Workspace 1 is deleted')


def test_get_sample_via_data(sample_service):
    # Requirements:
    #
    # Users:
    # USER3 owner of workspace, creator of sample and links,
    # USER4 fetcher of data links
    #
    # Workspaces:
    # 12 - owned by USER3,  shared read with user4, one object
    upa = "12/1/1"
    token_owner = TOKEN3
    user_owner = USER3
    token_user = TOKEN4
    sample_params_1 = CASE_01
    node_id_1 = get_sample_node_id(sample_params_1)
    sample_params_2 = CASE_02
    node_id_2 = get_sample_node_id(sample_params_2)
    data_id = "column1"

    # create samples
    sample_id1 = assert_create_sample(
        sample_service["url"], token_owner, sample_params_1
    )
    sample_id2 = assert_create_sample(
        sample_service["url"], token_owner, sample_params_2
    )
    case2 = copy.deepcopy(sample_params_2)
    case2["sample"]["id"] = sample_id2
    assert_create_sample(sample_service["url"], token_owner, case2, 2)

    # create links
    assert_result_create_link(
        sample_service["url"],
        token_owner,
        {"id": sample_id1, "version": 1, "node": node_id_1, "upa": upa},
        USER3,
    )

    assert_result_create_link(
        sample_service["url"],
        token_owner,
        {
            "id": sample_id2,
            "version": 2,
            "node": node_id_2,
            "upa": upa,
            "dataid": data_id,
        },
        USER3,
    )

    # get first sample via link from object using a token that has no access
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=token_user
    )
    result_01 = sample_service_client.call_assert_result(
        "get_sample_via_data", {"upa": upa, "id": sample_id1, "version": 1}
    )

    assert_ms_epoch_close_to_now(result_01["save_date"])
    del result_01["save_date"]

    assert result_01 == make_expected_sample(sample_params_1, sample_id1, user_owner, 1)

    # get second sample via link from object using a token that has no access
    result_02 = sample_service_client.call_assert_result(
        "get_sample_via_data", {"upa": upa, "id": sample_id2, "version": 2}
    )

    assert_ms_epoch_close_to_now(result_02["save_date"])
    del result_02["save_date"]

    assert result_02 == make_expected_sample(
        sample_params_2, sample_id2, user_owner, version=2
    )


def test_get_sample_via_data_expired_with_anon_user(sample_service):
    # Requirements:
    #
    # Users:
    # USER1 owner of workspace, creator of sample and links,
    #
    # Workspaces:
    # 8 - owned by USER1,  shared with no-one, shared global read, one object
    upa = "8/1/1"
    token_owner = TOKEN1
    user_owner = USER1
    sample_params_1 = CASE_01
    node_id_1 = get_sample_node_id(sample_params_1)
    sample_params_2 = CASE_02
    node_id_2 = get_sample_node_id(sample_params_2)
    data_id = "yay"

    # create samples
    sample_id1 = assert_create_sample(
        sample_service["url"], token_owner, sample_params_1
    )
    sample_id2 = assert_create_sample(
        sample_service["url"], token_owner, sample_params_2
    )

    # create links
    assert_result_create_link(
        sample_service["url"],
        token_owner,
        {
            "id": sample_id1,
            "version": 1,
            "node": node_id_1,
            "upa": upa,
            "dataid": data_id,
        },
        user_owner,
    )

    # update link node
    assert_result_create_link(
        sample_service["url"],
        TOKEN1,
        {
            "id": sample_id2,
            "version": 1,
            "node": node_id_2,
            "upa": upa,
            "dataid": data_id,
            "update": 1,
        },
        user_owner,
    )

    # pulled link from server to check the old link was expired

    # get sample via current link
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=token_owner
    )
    result = sample_service_client.call_assert_result(
        "get_sample_via_data", {"upa": upa, "id": sample_id2, "version": 1}
    )

    assert_ms_epoch_close_to_now(result["save_date"])
    del result["save_date"]

    assert result == make_expected_sample(
        sample_params_2, sample_id2, user_owner, version=1
    )

    # get sample via expired link
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=None
    )
    result_2 = sample_service_client.call_assert_result(
        "get_sample_via_data", {"upa": upa, "id": sample_id1, "version": 1}
    )

    assert_ms_epoch_close_to_now(result_2["save_date"])
    del result_2["save_date"]

    assert result_2 == make_expected_sample(
        sample_params_1, sample_id1, user_owner, version=1
    )


def test_get_sample_via_data_public_read(sample_service):
    # Requirements:
    #
    # Users:
    # USER1 owner of workspace, creator of sample and links,
    #
    # Workspaces:
    # 8 - owned by USER1,  shared with no-one, shared global read, one object
    upa = "8/1/1"
    token_owner = TOKEN1
    user_owner = USER1
    sample_params = CASE_01
    node_id = get_sample_node_id(sample_params)

    # create samples
    sample_id = assert_create_sample(sample_service["url"], token_owner, sample_params)

    # create links
    assert_result_create_link(
        sample_service["url"],
        token_owner,
        {"id": sample_id, "version": 1, "node": node_id, "upa": upa},
        user_owner,
    )

    # get sample via link from object using a token that has no explicit access
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=token_owner
    )
    result = sample_service_client.call_assert_result(
        "get_sample_via_data", {"upa": upa, "id": sample_id, "version": 1}
    )

    assert_ms_epoch_close_to_now(result["save_date"])
    del result["save_date"]

    assert result == make_expected_sample(
        sample_params, sample_id, user_owner, version=1
    )


def test_get_sample_via_data_fail(sample_service):
    # Requirements:
    #
    # Users:
    # USER3 owner of workspace, creator of sample and links,
    # USER4 unrelated user, no access to workspace or sample
    #
    # Workspaces:
    # 10 - owned by USER3,  shared with no-one, one object

    # Test Parameters
    sample_params = CASE_01
    upa = "4/1/1"
    token_owner = TOKEN3
    user_owner = USER3
    token_unauth = TOKEN4
    user_unauth = USER4
    invalid_upa = "4/2/1"
    invalid_sample_id = str(uuid.uuid4())
    data_id = "yay"

    def assert_error_get_sample_via_data(token, params, expected):
        sample_service_client = ServiceClient(
            "SampleService", url=sample_service["url"], token=token
        )
        error = sample_service_client.call_assert_error("get_sample_via_data", params)
        assert error["message"] == expected

    # create samples
    sample_id = assert_create_sample(sample_service["url"], token_owner, sample_params)

    # create links
    assert_result_create_link(
        sample_service["url"],
        token_owner,
        {"id": sample_id, "version": 1, "node": "root", "upa": upa, "dataid": data_id},
        user_owner,
    )

    # Parameter errors
    assert_error_get_sample_via_data(
        token_owner, {}, "Sample service error code 30000 Missing input parameter: upa"
    )
    assert_error_get_sample_via_data(
        token_owner,
        {"upa": upa},
        "Sample service error code 30000 Missing input parameter: id",
    )
    assert_error_get_sample_via_data(
        token_owner,
        {"upa": upa, "id": sample_id},
        "Sample service error code 30000 Missing input parameter: version",
    )

    # Permissions errors
    assert_error_get_sample_via_data(
        token_unauth,
        {"upa": upa, "id": sample_id, "version": 1},
        (
            "Sample service error code 20000 Unauthorized: "
            f"User {user_unauth} cannot read upa {upa}"
        ),
    )
    assert_error_get_sample_via_data(
        None,
        {"upa": upa, "id": sample_id, "version": 1},
        (
            "Sample service error code 20000 Unauthorized: "
            f"Anonymous users cannot read upa {upa}"
        ),
    )

    # Invalid params errors
    assert_error_get_sample_via_data(
        token_owner,
        {"upa": invalid_upa, "id": sample_id, "version": 1},
        (
            "Sample service error code 50040 No such workspace data: "
            f"Object {invalid_upa} does not exist"
        ),
    )

    assert_error_get_sample_via_data(
        token_owner,
        {"upa": upa, "id": invalid_sample_id, "version": 1},
        (
            "Sample service error code 50050 No such data link: "
            f"There is no link from UPA {upa} to sample {invalid_sample_id}"
        ),
    )
    assert_error_get_sample_via_data(
        token_owner,
        {"upa": upa, "id": sample_id, "version": 2},
        (
            "Sample service error code 50020 No such sample version: "
            f"{sample_id} ver 2"
        ),
    )


def test_get_data_link(sample_service):
    # Requirements:
    #
    # Users:
    # USER3 owner of workspace, creator of sample and links,
    # USER4 unrelated user, no access to workspace or sample
    #
    # Workspaces:
    # 4 - owned by USER3,  shared with no-one, one object

    # Test Parameters
    sample_params = CASE_01
    node_id = sample_params["sample"]["node_tree"][0]["id"]
    upa = "4/1/1"
    token_owner = TOKEN3
    user_owner = USER3
    data_id = "yay"
    token_fulladmin = TOKEN5

    # create samples
    sample_id = assert_create_sample(sample_service["url"], token_owner, sample_params)

    # create link
    link_id = assert_result_create_link(
        sample_service["url"],
        token_owner,
        {"id": sample_id, "version": 1, "node": node_id, "upa": upa, "dataid": data_id},
        user_owner,
    )

    # get link, user 3 has admin read perms
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=token_owner
    )
    result = sample_service_client.call_assert_result(
        "get_data_link", {"linkid": link_id}
    )

    created = result.pop("created")
    assert_ms_epoch_close_to_now(created)
    assert result == {
        "linkid": link_id,
        "id": sample_id,
        "version": 1,
        "node": node_id,
        "upa": upa,
        "dataid": data_id,
        "createdby": user_owner,
        "expiredby": None,
        "expired": None,
    }

    # expire link
    sample_service_client.call_assert_result(
        "expire_data_link", {"upa": upa, "dataid": data_id}
    )

    # get link, user 5 has full admin perms
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=token_fulladmin
    )
    link = sample_service_client.call_assert_result(
        "get_data_link", {"linkid": link_id}
    )

    assert_ms_epoch_close_to_now(link["expired"])
    del link["expired"]
    assert link == {
        "linkid": link_id,
        "id": sample_id,
        "version": 1,
        "node": node_id,
        "upa": upa,
        "dataid": data_id,
        "created": created,
        "createdby": user_owner,
        "expiredby": user_owner,
    }


def test_get_data_link_fail(sample_service):
    # Requirements:
    #
    # Users:
    # USER3 owner of workspace, creator of sample and links,
    # USER4 unrelated user, no access to workspace or sample
    #
    # Workspaces:
    # 4 - owned by USER3,  shared with no-one, one object

    # Test Parameters
    sample_params = CASE_01
    node_id = get_sample_node_id(sample_params)
    upa = "4/1/1"
    token_owner = TOKEN3
    user_owner = USER3
    data_id = "yay"
    token_unauth = TOKEN4
    user_unauth = USER4
    bad_data_link_id = str(uuid.uuid4())

    def assert_error_get_data_link(token, params, expected):
        # could make a single method that just takes the service method name to DRY things up a bit
        sample_service_client = ServiceClient(
            "SampleService", url=sample_service["url"], token=token
        )
        error = sample_service_client.call_assert_error("get_data_link", params)
        assert error["message"] == expected

    # create samples
    sample_id = assert_create_sample(sample_service["url"], token_owner, sample_params)

    # create link
    link_id = assert_result_create_link(
        sample_service["url"],
        token_owner,
        {"id": sample_id, "version": 1, "node": node_id, "upa": upa, "dataid": data_id},
        user_owner,
    )

    # Missing parameters
    assert_error_get_data_link(
        token_owner,
        {},
        "Sample service error code 30000 Missing input parameter: linkid",
    )

    # Invalid access
    assert_error_get_data_link(
        token_unauth,
        {"linkid": link_id},
        (
            "Sample service error code 20000 Unauthorized: "
            f"User {user_unauth} does not have the necessary administration privileges "
            "to run method get_data_link"
        ),
    )

    # Invalid params
    assert_error_get_data_link(
        token_owner,
        {"linkid": bad_data_link_id},
        ("Sample service error code 50050 No such data link: " f"{bad_data_link_id}"),
    )
