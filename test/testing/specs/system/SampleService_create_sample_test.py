# These tests cover the integration of the entire system and do not go into details - that's
# what unit tests are for. As such, typically each method will get a single happy path test and
# a single unhappy path test unless otherwise warranted.

# Tests of the auth user lookup and workspace wrapper code are at the bottom of the file.

import copy

from testing.shared.common import (
    assert_create_sample,
    assert_get_sample,
    check_kafka_messages,
    clear_kafka_messages,
    create_sample_assert_error,
    create_sample_assert_result,
    get_sample_assert_result,
    get_samples_assert_result,
    replace_acls,
    sample_params_to_sample,
)
from testing.shared.test_cases import CASE_00, CASE_01, CASE_02, CASE_03

#
# Simple sample creation cases. Does not assume anything else --
# see later tests for more complex scenarios.
#
from testing.shared.test_constants import (
    TOKEN1,
    TOKEN2,
    TOKEN3,
    TOKEN4,
    USER1,
    USER2,
    USER3,
    USER4,
)


def test_create_sample_one_string_field(sample_service):
    assert_create_sample(sample_service["url"], TOKEN1, CASE_01)


def test_create_sample_another_string_field(sample_service):
    sample_id = assert_create_sample(sample_service["url"], TOKEN1, CASE_02)
    assert_get_sample(sample_service["url"], TOKEN1, USER1, sample_id, 1, CASE_02)


def test_create_sample_prefix_field(sample_service):
    #
    # Requirements:
    # Users:
    # TOKEN1, USER1: Owner of sample
    #
    # Samples:
    # CASE_03: A sample with a prefix-key metadata field
    #
    result = create_sample_assert_result(
        sample_service["url"], TOKEN1, CASE_03, {"version": 1}
    )
    get_sample_assert_result(
        sample_service["url"],
        TOKEN1,
        {"id": result["id"], "version": 1},
        sample_params_to_sample(
            CASE_03, {"user": USER1, "id": result["id"], "version": 1}
        ),
    )


# Test versions


def test_create_sample_string_field_multiple_versions(sample_service):
    params = copy.deepcopy(CASE_01)
    for expected_sample_version in range(1, 5):
        result = create_sample_assert_result(
            sample_service["url"], TOKEN1, params, {"version": expected_sample_version}
        )
        get_sample_assert_result(
            sample_service["url"],
            TOKEN1,
            {"id": result["id"], "version": expected_sample_version},
            sample_params_to_sample(
                params,
                {"user": USER1, "id": result["id"], "version": expected_sample_version},
            ),
        )
        params["sample"]["id"] = result["id"]


def test_create_sample_then_get_sample(sample_service):
    result = create_sample_assert_result(
        sample_service["url"], TOKEN1, CASE_01, {"version": 1}
    )
    get_sample_assert_result(
        sample_service["url"],
        TOKEN1,
        {"id": result["id"], "version": 1},
        sample_params_to_sample(
            CASE_01, {"user": USER1, "id": result["id"], "version": 1}
        ),
    )


#
# Create one or more samples and verify that the appropriate kafka messages are generated
#


def test_create_sample_kafka_message(sample_service, kafka_host):
    clear_kafka_messages(kafka_host)

    result = create_sample_assert_result(
        sample_service["url"], TOKEN1, CASE_01, {"version": 1}
    )
    get_sample_assert_result(
        sample_service["url"],
        TOKEN1,
        {"id": result["id"], "version": 1},
        sample_params_to_sample(
            CASE_01, {"user": USER1, "id": result["id"], "version": 1}
        ),
    )

    check_kafka_messages(
        kafka_host,
        [
            {"event_type": "NEW_SAMPLE", "sample_id": result["id"], "sample_ver": 1},
        ],
    )


def test_create_sample_string_field_two_versions_kafka(sample_service, kafka_host):
    clear_kafka_messages(kafka_host)

    params = copy.deepcopy(CASE_01)

    # First sample
    result = create_sample_assert_result(
        sample_service["url"], TOKEN1, params, {"version": 1}
    )
    get_sample_assert_result(
        sample_service["url"],
        TOKEN1,
        {"id": result["id"], "version": 1},
        sample_params_to_sample(
            CASE_01, {"user": USER1, "id": result["id"], "version": 1}
        ),
    )
    params["sample"]["id"] = result["id"]

    # Subsequent samples
    for sample_version in range(2, 4):
        result = create_sample_assert_result(
            sample_service["url"], TOKEN1, params, {"version": sample_version}
        )
        get_sample_assert_result(
            sample_service["url"],
            TOKEN1,
            {"id": result["id"], "version": sample_version},
            sample_params_to_sample(
                CASE_01, {"user": USER1, "id": result["id"], "version": sample_version}
            ),
        )

    check_kafka_messages(
        kafka_host,
        [
            {"event_type": "NEW_SAMPLE", "sample_id": result["id"], "sample_ver": 1},
            {"event_type": "NEW_SAMPLE", "sample_id": result["id"], "sample_ver": 2},
            {"event_type": "NEW_SAMPLE", "sample_id": result["id"], "sample_ver": 3},
        ],
    )


#
# Create a sample as an admin
#


def create_sample_as_admin(url, create_token, as_user, get_token, expected_user):
    params = copy.deepcopy(CASE_01)
    params["as_admin"] = 1
    params["as_user"] = as_user

    sample_id = assert_create_sample(url, create_token, params)
    assert_get_sample(url, get_token, expected_user, sample_id, 1, params)


def test_create_sample_as_admin(sample_service):
    create_sample_as_admin(sample_service["url"], TOKEN2, None, TOKEN2, USER2)


def test_create_sample_as_admin_impersonate_user(sample_service):
    create_sample_as_admin(
        sample_service["url"], TOKEN2, "     " + USER4 + "      ", TOKEN4, USER4
    )


#
# Create a sample as an admin, multiple versions
#


def create_sample_version_as_admin(url, admin_token, as_user, get_token, expected_user):
    # Create version 1
    params = copy.deepcopy(CASE_01)
    params["as_admin"] = 1
    params["as_user"] = as_user

    sample_id = assert_create_sample(url, admin_token, params, 1)
    params["sample"]["id"] = sample_id
    sample_id = assert_create_sample(url, admin_token, params, 2)

    assert_get_sample(url, get_token, expected_user, sample_id, 2, params)


def test_create_sample_version_as_admin(sample_service):
    create_sample_version_as_admin(sample_service["url"], TOKEN2, None, TOKEN2, USER2)


def test_create_sample_version_as_admin_impersonate_user(sample_service):
    create_sample_version_as_admin(sample_service["url"], TOKEN2, USER3, TOKEN3, USER3)


#
# Error conditions
#


def test_create_sample_fail_no_nodes(sample_service):
    # Create base case params, remove the node_tree.
    params = copy.deepcopy(CASE_01)
    params["sample"]["node_tree"] = None
    error_message = (
        "Sample service error code 30001 Illegal input parameter: "
        "sample node tree must be present and a list"
    )

    create_sample_assert_error(
        sample_service["url"], TOKEN1, params, {"message": error_message}
    )


# TODO: There are many more cases of bad metadata we should cover here.
# numbers, min length, ontology (would need to mock ontology api)
def test_create_sample_fail_bad_metadata(sample_service):
    def create_sample_fail_bad_metadata(
        controlled_metadata, expected_error_message, source_meta=None
    ):
        params = copy.deepcopy(CASE_00)
        params["sample"]["node_tree"][0]["meta_controlled"] = controlled_metadata
        params["sample"]["node_tree"][0]["source_meta"] = source_meta

        create_sample_assert_error(
            sample_service["url"], TOKEN1, params, {"message": expected_error_message}
        )

    cases = [
        # Empty value object
        {
            "controlled_metadata": {"foo": {}},
            "expected_error_message": (
                "Sample service error code 30001 Illegal input parameter: "
                "Error for node at index 0: "
                "Controlled metadata value associated with metadata key foo is null or empty"
            ),
        },
        # Value set to None is a different error (although the message above implies otherwise)
        {
            "controlled_metadata": {"foo": None},
            "expected_error_message": (
                "Sample service error code 30001 Illegal input parameter: "
                "Node at index 0's controlled metadata entry does not have a "
                "dict as a value at key foo"
            ),
        },
        # The value of a value key cannot be null (aka None here)
        {
            "controlled_metadata": {"foo": {"value": None}},
            "expected_error_message": (
                "Sample service error code 30001 Illegal input parameter: "
                "Node at index 0's controlled metadata entry does not have a "
                "primitive type as the value at foo/value"
            ),
        },
        # The key may not be longer than the max-len, if no keys are provided for
        # the validator
        {
            "controlled_metadata": {"stringlentest": {"foooo": "barrrr"}},
            "expected_error_message": (
                "Sample service error code 30010 Metadata validation failed: Node at index 0: "
                "Key stringlentest: Metadata value at key foooo is longer than max length of 5"
            ),
        },
        # Tests that a string length is validated
        # TODO: the actual validation errors should be bundled elsewhere, and test all
        # validation contraints.
        {
            "controlled_metadata": {
                "stringlentest": {"foooo": "barrr", "spcky": "baz"}
            },
            "expected_error_message": (
                "Sample service error code 30010 Metadata validation failed: Node at index 0: Key "
                "stringlentest: Metadata value at key spcky is longer than max length of 2"
            ),
        },
        # Tests the max-len constraint for a prefix validator
        {
            "controlled_metadata": {"bark": {"fail_plz": "yes, or principal sayof"}},
            "expected_error_message": (
                "Sample service error code 30010 Metadata validation failed: "
                "Node at index 0: "
                "Prefix validator bar, key bark: {'subkey': 'fail_plz', "
                "'message': 'Metadata value at key fail_plz is longer than max length of 10'}"
            ),
        },
        # Tests duplicate source meta
        {
            "controlled_metadata": {"foo": {"foo": "bar"}},
            "expected_error_message": (
                "Sample service error code 30001 Illegal input parameter: Error for node at "
                "index 0: Duplicate source metadata key: foo"
            ),
            "source_meta": [
                {"key": "foo", "skey": "foo", "svalue": {"foo": "bar"}},
                {"key": "foo", "skey": "foo", "svalue": {"foo": "bar"}},
            ],
        },
    ]

    for case in cases:
        create_sample_fail_bad_metadata(
            case["controlled_metadata"],
            case["expected_error_message"],
            case.get("source_meta"),
        )


def test_create_sample_fail_permissions(sample_service):
    params = copy.deepcopy(CASE_01)

    # This one should work.
    result = create_sample_assert_result(
        sample_service["url"], TOKEN1, params, {"version": 1}
    )

    replace_acls(sample_service["url"], result["id"], TOKEN1, {"read": [USER2]})

    # This one will fail since USER2 doesn't have write permission.
    params["sample"]["id"] = result["id"]
    expected_error_message = (
        "Sample service error code 20000 Unauthorized: "
        f'User {USER2} cannot write to sample {result["id"]}'
    )
    create_sample_assert_error(
        sample_service["url"], TOKEN2, params, {"message": expected_error_message}
    )


def create_sample_fail_admin_as_user(url, user, expected_error_message):
    params = copy.deepcopy(CASE_01)
    params["as_admin"] = 1
    params["as_user"] = user

    create_sample_assert_error(url, TOKEN2, params, {"message": expected_error_message})


def test_create_sample_fail_admin_bad_user_name(sample_service):
    create_sample_fail_admin_as_user(
        sample_service["url"],
        "bad\tuser",
        (
            "Sample service error code 30001 Illegal input parameter: "
            "userid contains control characters"
        ),
    )


def test_create_sample_fail_admin_no_such_user(sample_service):
    create_sample_fail_admin_as_user(
        sample_service["url"],
        "impostor",
        ("Sample service error code 50000 No such user: " "impostor"),
    )


#
# Attempt to administratively create a sample for another user,
# using a token with read-only permission
# TOKEN3 = readadmin1 role
# USER4 = some other user,
#
def test_create_sample_fail_admin_permissions(sample_service):
    params = copy.deepcopy(CASE_01)
    params["as_admin"] = 1
    params["as_user"] = USER4

    expected_error_message = (
        "Sample service error code 20000 Unauthorized: "
        f"User {USER3} does not have the necessary administration privileges "
        "to run method create_sample"
    )
    create_sample_assert_error(
        sample_service["url"], TOKEN3, params, {"message": expected_error_message}
    )


def test_create_and_get_sample_with_version(sample_service, kafka_host):
    clear_kafka_messages(kafka_host)

    # version 1
    sample = create_sample_assert_result(
        sample_service["url"], TOKEN1, CASE_01, {"version": 1}
    )
    sample_id = sample["id"]

    # version 2

    params2 = copy.deepcopy(CASE_01)
    params2["sample"]["id"] = sample_id
    create_sample_assert_result(sample_service["url"], TOKEN1, params2, {"version": 2})

    # get version 1
    get_sample_assert_result(
        sample_service["url"],
        TOKEN1,
        {"id": sample_id, "version": 1},
        sample_params_to_sample(
            CASE_01, {"user": USER1, "id": sample_id, "version": 1}
        ),
    )

    # get version 2
    get_sample_assert_result(
        sample_service["url"],
        TOKEN1,
        {"id": sample_id, "version": 2},
        sample_params_to_sample(
            CASE_01, {"user": USER1, "id": sample_id, "version": 2}
        ),
    )

    check_kafka_messages(
        kafka_host,
        [
            {"event_type": "NEW_SAMPLE", "sample_id": sample_id, "sample_ver": 1},
            {"event_type": "NEW_SAMPLE", "sample_id": sample_id, "sample_ver": 2},
        ],
    )


def test_create_and_get_samples(sample_service, kafka_host):
    clear_kafka_messages(kafka_host)

    # first sample
    sample1 = create_sample_assert_result(
        sample_service["url"], TOKEN1, CASE_01, {"version": 1}
    )

    # second sample
    sample2 = create_sample_assert_result(
        sample_service["url"], TOKEN1, CASE_02, {"version": 1}
    )

    # get both samples
    get_samples_assert_result(
        sample_service["url"],
        TOKEN1,
        {
            "samples": [
                {"id": sample1["id"], "version": 1},
                {"id": sample2["id"], "version": 1},
            ]
        },
        [
            sample_params_to_sample(
                CASE_01, {"user": USER1, "id": sample1["id"], "version": 1}
            ),
            sample_params_to_sample(
                CASE_02, {"user": USER1, "id": sample2["id"], "version": 1}
            ),
        ],
    )

    check_kafka_messages(
        kafka_host,
        [
            {"event_type": "NEW_SAMPLE", "sample_id": sample1["id"], "sample_ver": 1},
            {"event_type": "NEW_SAMPLE", "sample_id": sample2["id"], "sample_ver": 1},
        ],
    )
