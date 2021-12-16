# These tests cover the integration of the entire system and do not go into details - that's
# what unit tests are for. As such, typically each method will get a single happy path test and
# a single unhappy path test unless otherwise warranted.
import copy
import uuid

from testing.shared.common import (
    VER,
    assert_acl_contents,
    assert_create_sample,
    assert_error_rpc_call,
    check_kafka_messages,
    clear_kafka_messages,
    create_generic_sample,
    create_sample_assert_result,
    get_sample_assert_result,
    replace_acls,
    rpc_call_result,
    sample_params_to_sample,
    update_acls,
)
from testing.shared.service_client import ServiceClient
from testing.shared.test_cases import CASE_01
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
    USER5,
    USER_NO_TOKEN1,
    USER_NO_TOKEN2,
    USER_NO_TOKEN3,
)
from testing.shared.test_utils import assert_ms_epoch_close_to_now


def test_status(sample_service):
    status = rpc_call_result(sample_service["url"], None, "status", [])

    assert_ms_epoch_close_to_now(status["servertime"])
    assert status["state"] == "OK"
    assert status["message"] == ""
    assert status["version"] == VER
    # ignore git url and hash, can change


def test_get_and_replace_acls(sample_service, kafka_host):
    clear_kafka_messages(kafka_host)

    sample_id = create_sample_assert_result(sample_service["url"], TOKEN1, CASE_01)[
        "id"
    ]

    assert_acl_contents(
        sample_service["url"],
        sample_id,
        TOKEN1,
        {"owner": USER1, "admin": [], "write": [], "read": [], "public_read": 0},
    )

    replace_acls(
        sample_service["url"],
        sample_id,
        TOKEN1,
        {
            "admin": [USER2],
            "write": [USER_NO_TOKEN1, USER_NO_TOKEN2, USER3],
            "read": [USER_NO_TOKEN3, USER4],
        },
    )

    # test that people in the acls can read
    for token in [TOKEN2, TOKEN3, TOKEN4]:
        assert_acl_contents(
            sample_service["url"],
            sample_id,
            token,
            {
                "owner": USER1,
                "admin": [USER2],
                "write": [USER3, USER_NO_TOKEN1, USER_NO_TOKEN2],
                "read": [USER4, USER_NO_TOKEN3],
                "public_read": 0,
            },
        )

        get_sample_assert_result(
            sample_service["url"],
            token,
            {"id": sample_id},
            sample_params_to_sample(
                CASE_01, {"user": USER1, "id": sample_id, "version": 1}
            ),
        )

    # test admins and writers can write
    for token, username, version in ((TOKEN2, USER2, 2), (TOKEN3, USER3, 3)):
        params = copy.deepcopy(CASE_01)
        params["sample"]["id"] = sample_id
        params["sample"]["name"] = f"test_sample_{version}"
        params["sample"]["node_tree"][0]["id"] = f"root_{version}"
        create_sample_assert_result(
            sample_service["url"], token, params, {"version": version}
        )

        get_sample_assert_result(
            sample_service["url"],
            TOKEN1,
            {"id": sample_id, "version": version},
            sample_params_to_sample(
                params, {"user": username, "id": sample_id, "version": version}
            ),
        )

    # test that an admin can replace ACLs
    replace_acls(
        sample_service["url"],
        sample_id,
        TOKEN2,
        {"admin": [USER_NO_TOKEN2], "write": [], "read": [USER2], "public_read": 1},
    )

    assert_acl_contents(
        sample_service["url"],
        sample_id,
        TOKEN1,
        {
            "owner": USER1,
            "admin": [USER_NO_TOKEN2],
            "write": [],
            "read": [USER2],
            "public_read": 1,
        },
    )

    check_kafka_messages(
        kafka_host,
        [
            {"event_type": "NEW_SAMPLE", "sample_id": sample_id, "sample_ver": 1},
            {"event_type": "ACL_CHANGE", "sample_id": sample_id},
            {"event_type": "NEW_SAMPLE", "sample_id": sample_id, "sample_ver": 2},
            {"event_type": "NEW_SAMPLE", "sample_id": sample_id, "sample_ver": 3},
            {"event_type": "ACL_CHANGE", "sample_id": sample_id},
        ],
    )


def test_get_acls_public_read(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)

    replace_acls(sample_service["url"], sample_id, TOKEN1, {"public_read": 1})

    for token in [TOKEN4, None]:  # user with no explicit perms and anon user
        assert_acl_contents(
            sample_service["url"],
            sample_id,
            token,
            {"owner": USER1, "admin": [], "write": [], "read": [], "public_read": 1},
        )


def test_get_acls_as_admin(sample_service):
    sample_id = assert_create_sample(sample_service["url"], TOKEN1, CASE_01, 1)

    # user 3 has admin read rights only
    assert_acl_contents(
        sample_service["url"],
        sample_id,
        TOKEN3,
        {"owner": USER1, "admin": [], "write": [], "read": [], "public_read": 0},
        as_admin=1,
    )


def test_replace_acls_as_admin(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)

    assert_acl_contents(
        sample_service["url"],
        sample_id,
        TOKEN1,
        {"owner": USER1, "admin": [], "write": [], "read": [], "public_read": 0},
    )

    replace_acls(
        sample_service["url"],
        sample_id,
        TOKEN2,
        {
            "admin": [USER2],
            "write": [USER_NO_TOKEN1, USER_NO_TOKEN2, USER3],
            "read": [USER_NO_TOKEN3, USER4],
            "public_read": 1,
        },
        as_admin=1,
    )

    assert_acl_contents(
        sample_service["url"],
        sample_id,
        TOKEN1,
        {
            "owner": USER1,
            "admin": [USER2],
            "write": [USER_NO_TOKEN1, USER_NO_TOKEN2, USER3],
            "read": [USER_NO_TOKEN3, USER4],
            "public_read": 1,
        },
    )


def test_get_acls_fail_no_id(sample_service):
    assert_error_rpc_call(
        sample_service["url"],
        TOKEN1,
        "get_sample_acls",
        [{}],
        "Sample service error code 30000 Missing input parameter: id",
    )


def test_get_acls_fail_permissions(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)

    assert_error_rpc_call(
        sample_service["url"],
        TOKEN2,
        "get_sample_acls",
        [{"id": sample_id}],
        f"Sample service error code 20000 Unauthorized: User user2 cannot read sample {sample_id}",
    )

    assert_error_rpc_call(
        sample_service["url"],
        None,
        "get_sample_acls",
        [{"id": sample_id}],
        (
            "Sample service error code 20000 Unauthorized: "
            f"Anonymous users cannot read sample {sample_id}"
        ),
    )

    assert_error_rpc_call(
        sample_service["url"],
        None,
        "get_sample_acls",
        [{"id": sample_id, "as_admin": 1}],
        (
            "Sample service error code 20000 Unauthorized: Anonymous users "
            "may not act as service administrators."
        ),
    )


def test_get_acls_fail_admin_permissions(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)

    assert_error_rpc_call(
        sample_service["url"],
        TOKEN4,
        "get_sample_acls",
        [{"id": sample_id, "as_admin": 1}],
        (
            "Sample service error code 20000 Unauthorized: User user4 does not have the "
            "necessary administration privileges to run method get_sample_acls"
        ),
    )


def test_replace_acls_fail_no_id(sample_service):
    assert_error_rpc_call(
        sample_service["url"],
        TOKEN1,
        "replace_sample_acls",
        [{}],
        "Sample service error code 30000 Missing input parameter: id",
    )


def test_replace_acls_fail_bad_acls(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)

    assert_error_rpc_call(
        sample_service["url"],
        TOKEN1,
        "replace_sample_acls",
        [{"id": sample_id, "acls": ["foo"]}],
        (
            "Sample service error code 30001 Illegal input parameter: "
            "ACLs must be supplied in the acls key and must be a mapping"
        ),
    )


def test_replace_acls_fail_permissions(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)

    replace_acls(
        sample_service["url"],
        sample_id,
        TOKEN1,
        {"admin": [USER2], "write": [USER3], "read": [USER4]},
    )

    for user, token in ((USER3, TOKEN3), (USER4, TOKEN4)):
        assert_error_rpc_call(
            sample_service["url"],
            token,
            "replace_sample_acls",
            [{"id": sample_id, "acls": {}}],
            (
                f"Sample service error code 20000 Unauthorized: User {user} cannot "
                f"administrate sample {sample_id}"
            ),
        )


def test_replace_acls_fail_admin_permissions(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)

    for user, token in ((USER3, TOKEN3), (USER4, TOKEN4)):
        assert_error_rpc_call(
            sample_service["url"],
            token,
            "replace_sample_acls",
            [{"id": sample_id, "acls": {}, "as_admin": 1}],
            (
                f"Sample service error code 20000 Unauthorized: User {user} does not have the "
                "necessary administration privileges to run method replace_sample_acls"
            ),
        )


def test_replace_acls_fail_bad_user(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)

    sample_service = ServiceClient(
        "SampleService", url=sample_service["url"], token=TOKEN1
    )
    invalid_admin_username = "a"
    invalid_read_username = "philbin_j_montgomery_iii"

    error = sample_service.call_assert_error(
        "replace_sample_acls",
        {
            "id": sample_id,
            "acls": {
                "admin": [USER2, invalid_admin_username],
                "write": [USER3],
                "read": [USER4, invalid_read_username],
            },
        },
    )
    error["message"] = (
        "Sample service error code 50000 No such user: "
        f"{invalid_admin_username}, {invalid_read_username}"
    )


def test_replace_acls_fail_user_in_2_acls(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)

    assert_error_rpc_call(
        sample_service["url"],
        TOKEN1,
        "replace_sample_acls",
        [{"id": sample_id, "acls": {"write": [USER2, USER3], "read": [USER2]}}],
        (
            "Sample service error code 30001 Illegal input parameter: "
            f"User {USER2} appears in two ACLs"
        ),
    )


def test_replace_acls_fail_owner_in_another_acl(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)

    assert_error_rpc_call(
        sample_service["url"],
        TOKEN1,
        "replace_sample_acls",
        [{"id": sample_id, "acls": {"write": [USER1]}}],
        (
            "Sample service error code 30001 Illegal input parameter: "
            "The owner cannot be in any other ACL"
        ),
    )


def test_update_acls(sample_service, kafka_host):
    def assert_update_acls(token, as_admin):
        clear_kafka_messages(kafka_host)
        sample_id = create_generic_sample(sample_service["url"], TOKEN1)

        replace_acls(
            sample_service["url"],
            sample_id,
            TOKEN1,
            {
                "admin": [USER2],
                "write": [USER_NO_TOKEN1, USER_NO_TOKEN2, USER3],
                "read": [USER_NO_TOKEN3, USER4],
                "public_read": 0,
            },
        )

        update_acls(
            sample_service["url"],
            token,
            {
                "id": sample_id,
                "admin": [USER4],
                "write": [USER2],
                "read": [USER_NO_TOKEN2],
                "remove": [USER3],
                "public_read": 390,
                "as_admin": 1 if as_admin else 0,
            },
        )

        assert_acl_contents(
            sample_service["url"],
            sample_id,
            TOKEN1,
            {
                "owner": USER1,
                "admin": [USER4],
                "write": [USER2, USER_NO_TOKEN1],
                "read": [USER_NO_TOKEN2, USER_NO_TOKEN3],
                "public_read": 1,
            },
        )

        check_kafka_messages(
            kafka_host,
            [
                {"event_type": "NEW_SAMPLE", "sample_id": sample_id, "sample_ver": 1},
                {"event_type": "ACL_CHANGE", "sample_id": sample_id},
                {"event_type": "ACL_CHANGE", "sample_id": sample_id},
            ],
        )

    assert_update_acls(TOKEN1, False)  # owner
    assert_update_acls(TOKEN2, False)  # admin
    assert_update_acls(TOKEN5, True)  # as_admin = True


def test_update_acls_with_at_least(sample_service, kafka_host):
    def update_acls_tst_with_at_least(token, as_admin):
        clear_kafka_messages(kafka_host)
        sample_id = create_generic_sample(sample_service["url"], TOKEN1)

        replace_acls(
            sample_service["url"],
            sample_id,
            TOKEN1,
            {
                "admin": [USER2],
                "write": [USER_NO_TOKEN1, USER_NO_TOKEN2, USER3],
                "read": [USER_NO_TOKEN3, USER4],
                "public_read": 0,
            },
        )

        update_acls(
            sample_service["url"],
            token,
            {
                "id": str(sample_id),
                "admin": [USER4],
                "write": [USER2, USER_NO_TOKEN3],
                "read": [USER_NO_TOKEN2, USER5],
                "remove": [USER3],
                "public_read": 390,
                "as_admin": 1 if as_admin else 0,
                "at_least": 1,
            },
        )

        assert_acl_contents(
            sample_service["url"],
            sample_id,
            TOKEN1,
            {
                "owner": USER1,
                "admin": [USER2, USER4],
                "write": [USER_NO_TOKEN1, USER_NO_TOKEN2, USER_NO_TOKEN3],
                "read": [USER5],
                "public_read": 1,
            },
        )

        check_kafka_messages(
            kafka_host,
            [
                {"event_type": "NEW_SAMPLE", "sample_id": sample_id, "sample_ver": 1},
                {"event_type": "ACL_CHANGE", "sample_id": sample_id},
                {"event_type": "ACL_CHANGE", "sample_id": sample_id},
            ],
        )

    update_acls_tst_with_at_least(TOKEN1, False)  # owner
    update_acls_tst_with_at_least(TOKEN2, False)  # admin
    update_acls_tst_with_at_least(TOKEN5, True)  # as_admin = True


def test_update_acls_fail_no_id(sample_service):
    assert_error_rpc_call(
        sample_service["url"],
        TOKEN1,
        "update_sample_acls",
        [{}],
        "Sample service error code 30000 Missing input parameter: id",
    )


def test_update_acls_fail_bad_pub(sample_service):
    assert_error_rpc_call(
        sample_service["url"],
        TOKEN1,
        "update_sample_acls",
        [{"id": str(uuid.uuid4()), "public_read": "thingy"}],
        (
            "Sample service error code 30001 Illegal input parameter: "
            "public_read must be an integer if present"
        ),
    )


def test_update_acls_fail_permissions(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)

    replace_acls(
        sample_service["url"],
        sample_id,
        TOKEN1,
        {"admin": [USER2], "write": [USER3], "read": [USER4]},
    )

    for user, token in ((USER3, TOKEN3), (USER4, TOKEN4)):
        assert_error_rpc_call(
            sample_service["url"],
            token,
            "update_sample_acls",
            [{"id": sample_id}],
            (
                "Sample service error code 20000 "
                f"Unauthorized: User {user} cannot administrate sample {sample_id}"
            ),
        )


def test_update_acls_fail_admin_permissions(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)
    for user, token in ((USER3, TOKEN3), (USER4, TOKEN4)):
        assert_error_rpc_call(
            sample_service["url"],
            token,
            "update_sample_acls",
            [{"id": sample_id, "as_admin": 1}],
            (
                f"Sample service error code 20000 Unauthorized: User {user} does not have the "
                "necessary administration privileges to run method update_sample_acls"
            ),
        )


def test_update_acls_fail_bad_user(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)
    invalid_admin_user = "invalidadminuser"
    invalid_write_username = "invalidwriteuser"
    invalid_read_username = "invalidreaduser"
    invalid_remove_username = "invalidremoveuser"
    assert_error_rpc_call(
        sample_service["url"],
        TOKEN1,
        "update_sample_acls",
        [
            {
                "id": sample_id,
                "admin": [USER2, invalid_admin_user],
                "write": [USER3, invalid_write_username],
                "read": [USER4, invalid_read_username],
                "remove": [invalid_remove_username],
            }
        ],
        (
            "Sample service error code 50000 No such user: "
            f"{invalid_admin_user}, {invalid_write_username}, "
            f"{invalid_read_username}, {invalid_remove_username}"
        ),
    )


def test_update_acls_fail_user_2_acls(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)
    assert_error_rpc_call(
        sample_service["url"],
        TOKEN1,
        "update_sample_acls",
        [
            {
                "id": sample_id,
                "admin": [USER2],
                "write": [USER3],
                "read": [USER4, USER2],
            }
        ],
        (
            "Sample service error code 30001 Illegal input parameter: "
            f"User {USER2} appears in two ACLs"
        ),
    )


def test_update_acls_fail_user_in_acl_and_remove(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)

    assert_error_rpc_call(
        sample_service["url"],
        TOKEN1,
        "update_sample_acls",
        [
            {
                "id": sample_id,
                "admin": [USER2],
                "write": [USER3],
                "read": [USER4],
                "remove": [USER2],
            }
        ],
        (
            "Sample service error code 30001 Illegal input parameter: "
            "Users in the remove list cannot be in any other ACL"
        ),
    )


def test_update_acls_fail_owner_in_another_acl(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)
    assert_error_rpc_call(
        sample_service["url"],
        TOKEN1,
        "update_sample_acls",
        [{"id": sample_id, "write": [USER1]}],
        (
            "Sample service error code 20000 Unauthorized: "
            f"ACLs for the sample owner {USER1} may not be modified by a delta update."
        ),
    )


def test_update_acls_fail_owner_in_remove_acl(sample_service):
    sample_id = create_generic_sample(sample_service["url"], TOKEN1)
    assert_error_rpc_call(
        sample_service["url"],
        TOKEN1,
        "update_sample_acls",
        [{"id": sample_id, "remove": [USER1]}],
        (
            "Sample service error code 20000 Unauthorized: "
            f"ACLs for the sample owner {USER1} may not be modified by a delta update."
        ),
    )
