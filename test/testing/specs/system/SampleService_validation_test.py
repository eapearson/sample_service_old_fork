# These tests cover the integration of the entire system and do not go into details - that's
# what unit tests are for. As such, typically each method will get a single happy path test and
# a single unhappy path test unless otherwise warranted.


# ###########################
# Validation tests
# Clearly these are incomplete!
# ###########################
from testing.shared.common import rpc_call_result
from testing.shared.test_constants import TOKEN2, USER2


def test_validate_sample(sample_service):
    def validate_sample_as_admin(as_user, get_token, expected_user):
        result = rpc_call_result(
            sample_service["url"],
            TOKEN2,
            "validate_samples",
            [
                {
                    "samples": [
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
                        }
                    ]
                }
            ],
        )
        assert "mysample" not in result["errors"]

    validate_sample_as_admin(None, TOKEN2, USER2)
