# These tests cover the integration of the entire system and do not go into details - that's
# what unit tests are for. As such, typically each method will get a single happy path test and
# a single unhappy path test unless otherwise warranted.

# Tests of the auth user lookup and workspace wrapper code are at the bottom of the file.
import copy
import uuid

from testing.shared.common import (
    assert_create_sample,
    create_link_assert_result,
    create_sample,
    create_sample_assert_result,
    get_sample_assert_error,
    get_sample_assert_result,
    get_sample_result,
    replace_acls,
    sample_params_to_sample,
)
from testing.shared.service_client import ServiceClient
from testing.shared.test_cases import CASE_01, CASE_02
from testing.shared.test_constants import (
    TOKEN1,
    TOKEN2,
    TOKEN3,
    TOKEN4,
    TOKEN6,
    USER1,
    USER2,
    USER3,
    USER4,
    USER6,
)
from testing.shared.test_utils import assert_ms_epoch_close_to_now


def test_get_sample_public_read(sample_service):
    sample = create_sample_assert_result(sample_service["url"], TOKEN1, CASE_01)

    replace_acls(sample_service["url"], sample["id"], TOKEN1, {"public_read": 1})

    for token in [TOKEN4, None]:  # unauthed user and anonymous user
        get_sample_assert_result(
            sample_service["url"],
            token,
            {"id": sample["id"], "version": 1},
            sample_params_to_sample(
                CASE_01, {"user": USER1, "id": sample["id"], "version": 1}
            ),
        )


def test_get_sample_as_admin(sample_service):
    # A normal user creates the sample.
    sample_id = create_sample(
        sample_service["url"],
        TOKEN1,
        {
            "name": "mysample",
            "node_tree": [
                {
                    "id": "root",
                    "type": "BioReplicate",
                    "meta_controlled": {"foo": {"bar": "baz"}},
                    "meta_user": {"a": {"b": "c"}},
                }
            ],
        },
    )

    # A read admin gets it.
    result = get_sample_result(sample_service["url"], TOKEN3, sample_id, 1, True)
    assert_ms_epoch_close_to_now(result["save_date"])
    del result["save_date"]

    assert result == {
        "id": sample_id,
        "version": 1,
        "user": USER1,
        "name": "mysample",
        "node_tree": [
            {
                "id": "root",
                "parent": None,
                "type": "BioReplicate",
                "meta_controlled": {
                    "foo": {"bar": "baz"},
                },
                "meta_user": {"a": {"b": "c"}},
                "source_meta": [],
            }
        ],
    }


def test_get_sample_fail_bad_id(sample_service):
    bad_sample_id = "foo"
    error = get_sample_assert_error(
        sample_service["url"],
        TOKEN2,
        {"id": bad_sample_id, "version": 1, "as_admin": False},
    )
    assert error["message"] == (
        "Sample service error code 30001 Illegal input parameter: "
        f"id {bad_sample_id} must be a UUID string"
    )


def test_get_sample_fail_missing_id(sample_service):
    bad_sample_id = str(uuid.uuid4())
    error = get_sample_assert_error(
        sample_service["url"],
        TOKEN2,
        {"id": bad_sample_id, "version": 1, "as_admin": False},
    )
    assert error["message"] == (
        "Sample service error code 50010 No such sample: " f"{bad_sample_id}"
    )


def test_get_sample_fail_permissions(sample_service):
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=TOKEN1
    )
    sample = sample_service_client.call_assert_result("create_sample", CASE_01)
    sample_id = sample["id"]

    error = get_sample_assert_error(
        sample_service["url"],
        TOKEN2,
        {"id": sample_id, "version": 1, "as_admin": False},
    )
    assert error["message"] == (
        "Sample service error code 20000 Unauthorized: "
        f'User {USER2} cannot read sample {sample["id"]}'
    )

    error = get_sample_assert_error(
        sample_service["url"], None, {"id": sample_id, "version": 1, "as_admin": False}
    )
    assert error["message"] == (
        "Sample service error code 20000 Unauthorized: "
        f"Anonymous users cannot read sample {sample_id}"
    )

    error = get_sample_assert_error(
        sample_service["url"], None, {"id": sample_id, "version": 1, "as_admin": True}
    )
    assert error["message"] == (
        "Sample service error code 20000 Unauthorized: "
        "Anonymous users may not act as service administrators."
    )


def test_get_sample_fail_admin_permissions(sample_service):
    # Create a sample as USER1
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=TOKEN1
    )
    sample = sample_service_client.call_assert_result("create_sample", CASE_01)

    # Attempt to fetch it administratively as user 4
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=TOKEN4
    )
    error = sample_service_client.call_assert_error(
        "get_sample", {"id": sample["id"], "version": 1, "as_admin": True}
    )
    assert error["message"] == (
        "Sample service error code 20000 Unauthorized: "
        f"User {USER4} does not have the necessary administration privileges to "
        "run method get_sample"
    )


def test_get_sample_via_data(sample_service):
    # create samples

    # Create a sample with one version
    sample1 = create_sample_assert_result(sample_service["url"], TOKEN3, CASE_01)

    # Create a second sample with two versions
    params2 = copy.deepcopy(CASE_02)
    sample2 = create_sample_assert_result(sample_service["url"], TOKEN3, params2)

    params2["sample"]["id"] = sample2["id"]
    create_sample_assert_result(sample_service["url"], TOKEN3, params2, {"version": 2})

    # create links

    create_link_assert_result(
        sample_service["url"],
        TOKEN3,
        {"id": sample1["id"], "version": 1, "node": "root", "upa": "1/1/1"},
        USER3,
    )

    create_link_assert_result(
        sample_service["url"],
        TOKEN3,
        {
            "id": sample2["id"],
            "version": 2,
            "node": "root2",
            "upa": "1/1/1",
            "dataid": "column2",
        },
        USER3,
    )

    # get first sample via link from object 1/1/1 using a token that has no access
    # TODO: May need to make 1/1/1 public, or use 2/2/2 or focus this test further.
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=TOKEN4
    )
    sample1_via_data = sample_service_client.call_assert_result(
        "get_sample_via_data", {"upa": "1/1/1", "id": sample1["id"], "version": 1}
    )

    assert_ms_epoch_close_to_now(sample1_via_data["save_date"])
    del sample1_via_data["save_date"]

    assert sample1_via_data == sample_params_to_sample(
        CASE_01, {"id": sample1["id"], "version": 1, "user": USER3}
    )

    # get second sample via link from object 1/1/1 using a token that has no access

    sample2_via_data = sample_service_client.call_assert_result(
        "get_sample_via_data", {"upa": "1/1/1", "id": sample2["id"], "version": 2}
    )

    assert_ms_epoch_close_to_now(sample2_via_data["save_date"])
    del sample2_via_data["save_date"]

    assert sample2_via_data == sample_params_to_sample(
        CASE_02, {"id": sample2["id"], "user": USER3, "version": 2}
    )


def test_get_sample_via_data_expired_with_anon_user(sample_service):
    # Create a sample
    sample1 = create_sample_assert_result(sample_service["url"], TOKEN3, CASE_01)

    # Create a second sample
    sample2 = create_sample_assert_result(sample_service["url"], TOKEN3, CASE_02)

    # create link from first sample to an object
    create_link_assert_result(
        sample_service["url"],
        TOKEN3,
        {
            "id": sample1["id"],
            "version": 1,
            "node": "root",
            "upa": "2/2/2",
            "dataid": "yay",
        },
        USER3,
    )

    # update link from second sample to same object
    create_link_assert_result(
        sample_service["url"],
        TOKEN3,
        {
            "id": sample2["id"],
            "version": 1,
            "node": "root2",
            "upa": "2/2/2",
            "dataid": "yay",
            "update": 1,
        },
        USER3,
    )

    # pull link from server to check the old link was expired

    # get sample 2 via current link
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=None
    )
    sample2_via_data = sample_service_client.call_assert_result(
        "get_sample_via_data", {"upa": "2/2/2", "id": sample2["id"], "version": 1}
    )
    assert_ms_epoch_close_to_now(sample2_via_data["save_date"])
    del sample2_via_data["save_date"]

    assert sample2_via_data == sample_params_to_sample(
        CASE_02, {"id": sample2["id"], "user": USER3, "version": 1}
    )

    # get sample 1 via expired link
    sample1_via_data = sample_service_client.call_assert_result(
        "get_sample_via_data", {"upa": "2/2/2", "id": sample1["id"], "version": 1}
    )
    assert_ms_epoch_close_to_now(sample1_via_data["save_date"])
    del sample1_via_data["save_date"]

    expected_sample = sample_params_to_sample(
        CASE_01, {"id": sample1["id"], "user": USER3, "version": 1}
    )

    assert sample1_via_data == expected_sample


def test_get_sample_via_data_public_read(sample_service, workspace_url):
    sample1 = create_sample_assert_result(sample_service["url"], TOKEN1, CASE_01)
    publicly_readable_object_ref = "2/2/2"

    # create links
    create_link_assert_result(
        sample_service["url"],
        TOKEN1,
        {
            "id": sample1["id"],
            "version": 1,
            "node": "root",
            "upa": publicly_readable_object_ref,
        },
        USER1,
    )

    # get sample via link from object 1/1/1 using a token that has no explicit access
    sample_service_client = ServiceClient(
        "SampleService", url=sample_service["url"], token=TOKEN4
    )
    sample1_via_data = sample_service_client.call_assert_result(
        "get_sample_via_data",
        {"upa": publicly_readable_object_ref, "id": sample1["id"], "version": 1},
    )

    del sample1_via_data["save_date"]

    expected_sample = sample_params_to_sample(
        CASE_01, {"id": sample1["id"], "version": 1, "user": USER1}
    )
    assert sample1_via_data == expected_sample


def test_get_sample_via_data_fail(sample_service):
    def assert_fail_get_sample_via_data(token, params, expected_message):
        sample_service_client = ServiceClient(
            "SampleService", url=sample_service["url"], token=token
        )
        error = sample_service_client.call_assert_error("get_sample_via_data", params)
        assert error["message"] == expected_message

    # create samples
    sample_id = assert_create_sample(sample_service["url"], TOKEN3, CASE_01)

    # create a like to poke at in the tests.
    create_link_assert_result(
        sample_service["url"],
        TOKEN3,
        {
            "id": sample_id,
            "version": 1,
            "node": "root",
            "upa": "1/1/1",
            "dataid": "yay",
        },
        USER3,
    )

    assert_fail_get_sample_via_data(
        TOKEN3, {}, "Sample service error code 30000 Missing input parameter: upa"
    )
    assert_fail_get_sample_via_data(
        TOKEN3,
        {"upa": "1/1/1"},
        "Sample service error code 30000 Missing input parameter: id",
    )
    assert_fail_get_sample_via_data(
        TOKEN3,
        {"upa": "1/1/1", "id": sample_id},
        "Sample service error code 30000 Missing input parameter: version",
    )
    assert_fail_get_sample_via_data(
        TOKEN6,
        {"upa": "1/1/1", "id": sample_id, "version": 1},
        f"Sample service error code 20000 Unauthorized: User {USER6} cannot read upa 1/1/1",
    )
    assert_fail_get_sample_via_data(
        None,
        {"upa": "1/1/1", "id": sample_id, "version": 1},
        "Sample service error code 20000 Unauthorized: Anonymous users cannot read upa 1/1/1",
    )
    assert_fail_get_sample_via_data(
        TOKEN3,
        {"upa": "1/100/1", "id": sample_id, "version": 1},
        "Sample service error code 50040 No such workspace data: Object 1/100/1 does not exist",
    )
    badid = uuid.uuid4()
    assert_fail_get_sample_via_data(
        TOKEN3,
        {"upa": "1/1/1", "id": str(badid), "version": 1},
        "Sample service error code 50050 No such data link: There is no link from UPA 1/1/1 "
        + f"to sample {badid}",
    )
    assert_fail_get_sample_via_data(
        TOKEN3,
        {"upa": "1/1/1", "id": sample_id, "version": 2},
        f"Sample service error code 50020 No such sample version: {sample_id} ver 2",
    )
