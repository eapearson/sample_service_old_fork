# These tests cover the integration of the entire system and do not go into details - that's
# what unit tests are for. As such, typically each method will get a single happy path test and
# a single unhappy path test unless otherwise warranted.

# Tests of the auth user lookup and workspace wrapper code are at the bottom of the file.


from testing.shared.service_client import ServiceClient

#
# Helpers
#


def assert_result_get_metadata_key_static_metadata(url, params, expected):
    sample_service_client = ServiceClient("SampleService", url=url, token=None)
    result = sample_service_client.call_assert_result(
        "get_metadata_key_static_metadata", params
    )
    assert result == {"static_metadata": expected}
    return result


def assert_error_get_metadata_key_static_metadata(url, params, error):
    sample_service_client = ServiceClient("SampleService", url=url, token=None)
    error = sample_service_client.call_assert_error(
        "get_metadata_key_static_metadata", params
    )
    error["message"] == error


#
# Tests
#


def test_get_metadata_key_static_metadata(sample_service):
    assert_result_get_metadata_key_static_metadata(
        sample_service["url"], {"keys": ["foo"]}, {"foo": {"a": "b", "c": "d"}}
    )
    assert_result_get_metadata_key_static_metadata(
        sample_service["url"],
        {"keys": ["foo", "stringlentest"], "prefix": 0},
        {"foo": {"a": "b", "c": "d"}, "stringlentest": {"h": "i", "j": "k"}},
    )


def test_get_metadata_key_static_metadata_prefix(sample_service):
    assert_result_get_metadata_key_static_metadata(
        sample_service["url"],
        {"keys": ["bar"], "prefix": 1},
        {"bar": {"a": "b", "c": 1}},
    )
    assert_result_get_metadata_key_static_metadata(
        sample_service["url"],
        {"keys": ["bark"], "prefix": 2},
        {"bar": {"a": "b", "c": 1}},
    )


def test_get_metadata_key_static_metadata_fail_bad_args(sample_service):
    assert_error_get_metadata_key_static_metadata(
        sample_service["url"],
        {},
        "Sample service error code 30001 Illegal input parameter: keys must be a list",
    )
    assert_error_get_metadata_key_static_metadata(
        sample_service["url"],
        {"keys": ["foo", "stringlentestage"], "prefix": 0},
        "Sample service error code 30001 Illegal input parameter: No such metadata key: "
        + "stringlentestage",
    )


def test_get_metadata_key_static_metadata_fail_bad_args_prefix(sample_service):
    assert_error_get_metadata_key_static_metadata(
        sample_service["url"],
        {"keys": ["bark"], "prefix": 1},
        "Sample service error code 30001 Illegal input parameter: No such prefix metadata key: "
        + "bark",
    )
    assert_error_get_metadata_key_static_metadata(
        sample_service["url"],
        {"keys": ["baz"], "prefix": 2},
        "Sample service error code 30001 Illegal input parameter: No prefix metadata keys "
        + "matching key baz",
    )
