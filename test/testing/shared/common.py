import copy
import datetime
import json
import os
import tempfile
import uuid
from configparser import ConfigParser

import requests
import yaml
from kafka import KafkaConsumer
from testing.shared import test_utils
from testing.shared.service_client import ServiceClient

# ??
from testing.shared.test_cases import CASE_01
from testing.shared.test_constants import (
    ARANGODB_PORT,
    KAFKA_PORT,
    KAFKA_TOPIC,
    MOCK_SERVICES_PORT,
    TEST_COL_DATA_LINK,
    TEST_COL_NODE_EDGE,
    TEST_COL_NODES,
    TEST_COL_SAMPLE,
    TEST_COL_SCHEMA,
    TEST_COL_VER_EDGE,
    TEST_COL_VERSION,
    TEST_COL_WS_OBJ_VER,
    TEST_DB_NAME,
    TEST_PWD,
    TEST_USER,
    TOKEN2,
    TOKEN_SERVICE,
    TOKEN_WS_READ_ADMIN,
)
from testing.shared.test_utils import assert_ms_epoch_close_to_now

VER = "0.1.0-alpha28"


def replace_acls(url, sample_id, token, acls, as_admin=0, debug=False):
    response = requests.post(
        url,
        headers=get_authorized_headers(token),
        json=make_rpc(
            "replace_sample_acls",
            [{"id": sample_id, "acls": acls, "as_admin": as_admin}],
        ),
    )
    if debug:
        print(response.text)
    assert response.ok is True

    assert response.json() == make_result(None)


def assert_acl_contents(url, sample_id, token, expected, as_admin=0, print_resp=False):
    params = [{"id": sample_id, "as_admin": as_admin}]
    result = rpc_call_result(url, token, "get_sample_acls", params)

    for key in ["admin", "write", "read"]:
        assert sorted(result[key]) == sorted(expected[key])

    for key in ["owner", "public_read"]:
        assert result[key] == expected[key]


def get_authorized_headers(token):
    headers = {"accept": "application/json"}
    if token is not None:
        headers["authorization"] = token
    return headers


def check_kafka_messages(kafka_host, expected_msgs, topic=KAFKA_TOPIC, print_res=False):
    kc = KafkaConsumer(
        topic,
        bootstrap_servers=kafka_host,
        auto_offset_reset="earliest",
        group_id="foo",
    )  # quiets warnings

    try:
        res = kc.poll(timeout_ms=2000)  # 1s not enough? Seems like a lot
        if print_res:
            print(res)
        assert len(res) == 1
        assert next(iter(res.keys())).topic == topic
        records = next(iter(res.values()))
        assert len(records) == len(expected_msgs)
        for i, r in enumerate(records):
            assert json.loads(r.value) == expected_msgs[i]
        # Need to commit here? doesn't seem like it
    finally:
        kc.close()


def clear_kafka_messages(kafka_host, topic=KAFKA_TOPIC):
    kc = KafkaConsumer(
        topic,
        bootstrap_servers=kafka_host,
        auto_offset_reset="earliest",
        group_id="foo",
    )  # quiets warnings

    try:
        kc.poll(timeout_ms=2000)  # 1s not enough? Seems like a lot
        # Need to commit here? doesn't seem like it
    finally:
        kc.close()


def _validate_sample_as_admin(url, as_user, get_token, expected_user):
    ret = requests.post(
        url,
        headers=get_authorized_headers(TOKEN2),
        json={
            "method": "SampleService.validate_samples",
            "version": "1.1",
            "id": "67",
            "params": [
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
        },
    )
    assert ret.ok is True
    ret_json = ret.json()["result"][0]
    assert "mysample" not in ret_json["errors"]


# def _get_sample_fail(url, token, params, expected):
#     # user 4 has no admin permissions
#     ret = requests.post(url, headers=get_authorized_headers(token), json={
#         'method': 'SampleService.get_sample',
#         'version': '1.1',
#         'id': '42',
#         'params': [params]
#     })
#
#     assert ret.status_code == 500
#     assert ret.json()['error']['message'] == expected


def _get_current_epochmillis():
    return round(datetime.datetime.now(tz=datetime.timezone.utc).timestamp() * 1000)


def create_generic_sample(url, token):
    ret = requests.post(
        url,
        headers=get_authorized_headers(token),
        json=make_rpc("create_sample", [CASE_01]),
    )
    assert ret.ok is True
    assert ret.json()["result"][0]["version"] == 1
    return ret.json()["result"][0]["id"]


def rpc_call(url, token, method, params, debug=False):
    response = requests.post(
        url, headers=get_authorized_headers(token), json=make_rpc(method, params)
    )
    if debug:
        print("[rpc_call_result]", params, response.text)
    return response


def rpc_call_result(url, token, method, params, debug=False):
    response = rpc_call(url, token, method, params, debug)
    assert response.ok is True
    payload = response.json()
    assert "result" in payload
    result = response.json()["result"]

    # The result may be either null or an array of one element
    # containing the result data.
    if result is None:
        return result

    assert type(result) is list
    assert len(result) == 1
    return result[0]


def rpc_call_error(url, token, method, params, debug=False):
    response = rpc_call(url, token, method, params, debug)
    assert response.status_code == 500
    return response.json()["error"]


def assert_error_rpc_call(url, token, method, params, expected_message, debug=False):
    response = rpc_call(url, token, method, params, debug)
    if debug:
        print("[assert_error_rpc_call]", expected_message)
    assert response.status_code == 500
    error = response.json()["error"]
    if debug:
        print("[assert_error_rpc_call]", error["message"], expected_message)
    assert error["message"] == expected_message
    return error


def assert_result_rpc_call(url, token, method, params, expected_result, debug=False):
    result = rpc_call_result(url, token, method, params, debug)
    assert result == expected_result
    return result


# def get_acls_fail_permissions(service_port, token, params, expected):
#     return assert_error_rpc_call(service_port, token, [])
#     ret = requests.post(url, headers=get_authorized_headers(token), json={
#         'method': 'SampleService.get_sample_acls',
#         'version': '1.1',
#         'id': '42',
#         'params': [params]
#     })
#     assert ret.status_code == 500
#     assert ret.json()['error']['message'] == expected


def _request_fail(url, method, token, params, expected):
    ret = requests.post(
        url,
        headers=get_authorized_headers(token),
        json={
            "method": "SampleService." + method,
            "version": "1.1",
            "id": "42",
            "params": [params],
        },
    )
    assert ret.status_code == 500
    assert ret.json()["error"]["message"] == expected


# def get_sample_via_data(service_port, token, params):
#     sample = rpc_call_result(service_port, token, 'get_sample_via_data', [params])
#     assert_ms_epoch_close_to_now(sample['save_date'])
#     return sample


def create_link(url, token, params, expected_user, print_resp=False):
    result = rpc_call_result(url, token, "create_data_link", [params])
    link = result["new_link"]
    link_id = link["linkid"]
    uuid.UUID(link_id)  # check the ID is a valid UUID
    del link["linkid"]
    created = link["created"]
    assert_ms_epoch_close_to_now(created)
    del link["created"]
    assert link == {
        "id": params["id"],
        "version": params["version"],
        "node": params["node"],
        "upa": params["upa"],
        "dataid": params.get("dataid"),
        "createdby": expected_user,
        "expiredby": None,
        "expired": None,
    }
    return link_id


def assert_result_create_link(url, token, params, expected_user, debug=False):
    result = rpc_call_result(url, token, "create_data_link", [params], debug)
    link = result["new_link"]
    link_id = link["linkid"]
    uuid.UUID(link_id)  # check the ID is a valid UUID
    del link["linkid"]
    created = link["created"]
    assert_ms_epoch_close_to_now(created)
    del link["created"]
    assert link == {
        "id": params["id"],
        "version": params["version"],
        "node": params["node"],
        "upa": params["upa"],
        "dataid": params.get("dataid"),
        "createdby": expected_user,
        "expiredby": None,
        "expired": None,
    }
    return link_id


def create_link_assert_result(url, token, params, expected_user, debug=False):
    result = rpc_call_result(url, token, "create_data_link", [params], debug)

    link = copy.deepcopy(result["new_link"])

    uuid.UUID(link["linkid"])  # check the ID is a valid UUID
    del link["linkid"]

    assert_ms_epoch_close_to_now(link["created"])
    del link["created"]

    assert link == {
        "id": params["id"],
        "version": params["version"],
        "node": params["node"],
        "upa": params["upa"],
        "dataid": params.get("dataid"),
        "createdby": expected_user,
        "expiredby": None,
        "expired": None,
    }
    return result["new_link"]


def assert_error_create_link(url, token, params, expected_error_message):
    error = rpc_call_error(url, token, "create_data_link", [params])
    error["message"] == expected_error_message


def get_sample(url, token, sample_id, version=1, as_admin=False):
    return rpc_call(
        url,
        token,
        "get_sample",
        [{"id": str(sample_id), "version": version, "as_admin": as_admin}],
    )


def get_sample_result(url, token, sample_id, version=1, as_admin=False):
    return rpc_call_result(
        url,
        token,
        "get_sample",
        [{"id": str(sample_id), "version": version, "as_admin": as_admin}],
    )


def create_deploy_cfg():
    cfg = ConfigParser()
    ss = "SampleService"
    cfg.add_section(ss)

    cfg[ss]["auth-service-url"] = (
        f"http://mockservices:{MOCK_SERVICES_PORT}/services/auth/"
        + "api/legacy/KBase/Sessions/Login"
    )
    cfg[ss]["auth-service-url-allow-insecure"] = "true"

    cfg[ss]["auth-root-url"] = f"http://mockservices:{MOCK_SERVICES_PORT}/services/auth"
    cfg[ss]["auth-token"] = TOKEN_SERVICE
    cfg[ss]["auth-read-admin-roles"] = "readadmin1"
    cfg[ss]["auth-full-admin-roles"] = "fulladmin2"

    cfg[ss]["arango-url"] = f"http://arangodb:{ARANGODB_PORT}"
    cfg[ss]["arango-db"] = TEST_DB_NAME
    cfg[ss]["arango-user"] = TEST_USER
    cfg[ss]["arango-pwd"] = TEST_PWD

    cfg[ss]["workspace-url"] = f"http://mockservices:{MOCK_SERVICES_PORT}/serivces/ws"
    cfg[ss]["workspace-read-admin-token"] = TOKEN_WS_READ_ADMIN

    cfg[ss]["kafka-bootstrap-servers"] = f"kafka:{KAFKA_PORT}"
    cfg[ss]["kafka-topic"] = KAFKA_TOPIC

    cfg[ss]["sample-collection"] = TEST_COL_SAMPLE
    cfg[ss]["version-collection"] = TEST_COL_VERSION
    cfg[ss]["version-edge-collection"] = TEST_COL_VER_EDGE
    cfg[ss]["node-collection"] = TEST_COL_NODES
    cfg[ss]["node-edge-collection"] = TEST_COL_NODE_EDGE
    cfg[ss]["data-link-collection"] = TEST_COL_DATA_LINK
    cfg[ss]["workspace-object-version-shadow-collection"] = TEST_COL_WS_OBJ_VER
    cfg[ss]["schema-collection"] = TEST_COL_SCHEMA

    # sample - collection = samples_sample
    # version - collection = samples_version
    # version - edge - collection = samples_ver_edge
    # node - collection = samples_nodes
    # node - edge - collection = samples_nodes_edge
    # data - link - collection = samples_data_link
    # workspace - object - version - shadow - collection = ws_object_version
    # schema - collection = samples_schema

    # TODO: Move into a test data file
    metacfg = {
        "validators": {
            "foo": {
                "validators": [
                    {
                        "module": "SampleService.core.validator.builtin",
                        "callable_builder": "noop",
                    }
                ],
                "key_metadata": {"a": "b", "c": "d"},
            },
            "stringlentest": {
                "validators": [
                    {
                        "module": "SampleService.core.validator.builtin",
                        "callable_builder": "string",
                        "parameters": {"max-len": 5},
                    },
                    {
                        "module": "SampleService.core.validator.builtin",
                        "callable_builder": "string",
                        "parameters": {"keys": "spcky", "max-len": 2},
                    },
                ],
                "key_metadata": {"h": "i", "j": "k"},
            },
        },
        "prefix_validators": {
            "pre": {
                "validators": [
                    {
                        "module": "core.config_test_vals",
                        "callable_builder": "prefix_validator_test_builder",
                        "parameters": {"fail_on_arg": "fail_plz"},
                    }
                ],
                "key_metadata": {"1": "2"},
            }
        },
    }
    temp_file, temp_file_path = tempfile.mkstemp(
        ".cfg", "metaval-", dir=test_utils.get_temp_dir(), text=True
    )
    os.close(temp_file)

    with open(temp_file_path, "w") as handle:
        yaml.dump(metacfg, handle)

    cfg[ss]["metadata-validator-config-url"] = f"file://{temp_file_path}"

    deploy_file, deploy_file_path = tempfile.mkstemp(
        ".cfg", "deploy-", dir=test_utils.get_temp_dir(), text=True
    )
    os.close(deploy_file)

    with open(deploy_file_path, "w") as handle:
        cfg.write(handle)

    return deploy_file_path


def make_rpc(func, params):
    return {
        "method": f"SampleService.{func}",
        "version": "1.1",
        "id": "123",
        "params": params,
    }


def make_result(result):
    return {"version": "1.1", "id": "123", "result": result}


def make_error(error):
    return {"version": "1.1", "id": "123", "error": error}


#
# Create Sample
#


def create_sample(url, token, sample, expected_version=1, debug=False):
    result = rpc_call_result(url, token, "create_sample", [{"sample": sample}], debug)
    assert result["version"] == expected_version
    return result["id"]


def create_sample_result(url, token, sample, expected_version=1):
    result = rpc_call_result(url, token, "create_sample", [{"sample": sample}])
    assert result["version"] == expected_version
    return result


def create_sample_assert_result(
    url, token, params, expectations={"version": 1}, debug=False
):
    sample_service = ServiceClient("SampleService", url=url, token=token)
    result = sample_service.call_assert_result("create_sample", params, debug=debug)
    assert result["version"] == expectations["version"]
    return result


def create_sample_assert_error(url, token, params, expectations=None, debug=False):
    sample_service = ServiceClient("SampleService", url=url, token=token)
    error = sample_service.call_assert_error("create_sample", params, debug=debug)
    if expectations is not None:
        assert error["message"] == expectations["message"]
    return error


def create_sample_error(url, token, sample):
    return rpc_call_error(url, token, "create_sample", [{"sample": sample}])


def assert_create_sample(url, token, params, expected_version=1, debug=False):
    result = rpc_call_result(url, token, "create_sample", [params], debug)
    assert result["version"] == expected_version
    return result["id"]


def assert_fail_create_sample(url, token, params, error_message):
    response = requests.post(
        url,
        headers=get_authorized_headers(token),
        json=make_rpc("create_sample", [params]),
    )
    assert response.status == 500
    assert response.json()["error"]["message"] == error_message


def assert_get_sample(url, token, username, sample_id, sample_version, params):
    response = requests.post(
        url,
        headers=get_authorized_headers(token),
        json=make_rpc("get_sample", [{"id": sample_id, "version": sample_version}]),
    )
    assert response.ok is True
    result = response.json()["result"][0]

    # Test that the save data is sane, but remove it before an exact
    # dict match
    assert_ms_epoch_close_to_now(result["save_date"])
    del result["save_date"]

    expected = copy.deepcopy(params["sample"])
    expected["id"] = sample_id
    expected["user"] = username
    expected["version"] = sample_version
    expected["node_tree"][0]["parent"] = None

    assert result == expected


def sample_params_to_sample(params, update):
    """
    Given a sample params dict, and a set of fields to update, returns a dict
    which should be the same as that returned from the sample service for a
    sample created by said params.
    """
    expected = copy.deepcopy(params["sample"])
    expected["id"] = update["id"]
    expected["version"] = update["version"]
    expected["user"] = update["user"]
    expected["node_tree"][0]["parent"] = None
    return expected


def get_sample_assert_result(url, token, params, expected, debug=False):
    sample_service = ServiceClient("SampleService", url=url, token=token)
    sample = sample_service.call_assert_result("get_sample", params, debug=debug)

    # Test that the save data is sane, but remove it before an exact
    # dict match
    sample_to_compare = copy.deepcopy(sample)
    assert_ms_epoch_close_to_now(sample_to_compare["save_date"])
    del sample_to_compare["save_date"]

    assert sample_to_compare == expected
    return sample


def get_sample_assert_error(url, token, params, expected=None, debug=False):
    sample_service = ServiceClient("SampleService", url=url, token=token)
    error = sample_service.call_assert_error("get_sample", params, debug=debug)
    if expected is not None:
        assert expected["message"] == error["message"]
        # and more to come?
    return error


def get_samples_assert_result(url, token, params, expected, debug=False):
    sample_service = ServiceClient("SampleService", url=url, token=token)
    samples = sample_service.call_assert_result("get_samples", params, debug=debug)

    # Test that the save data is sane, but remove it before an exact
    # dict match
    samples_to_compare = copy.deepcopy(samples)
    for sample in samples_to_compare:
        assert_ms_epoch_close_to_now(sample["save_date"])
        del sample["save_date"]

    assert samples_to_compare == expected
    return samples


def update_acls_fail(url, token, params, expected):
    return assert_error_rpc_call(url, token, "update_sample_acls", [params], expected)


def update_acls(url, token, params):
    return assert_result_rpc_call(url, token, "update_sample_acls", [params], None)


def get_current_epochmillis():
    return round(datetime.datetime.now(tz=datetime.timezone.utc).timestamp() * 1000)


def make_expected_sample(case, sample_id, user, version=1):
    expected = copy.deepcopy(case["sample"])
    expected["id"] = sample_id
    expected["user"] = user
    expected["version"] = version
    expected["node_tree"][0]["parent"] = None
    return expected


def get_sample_node_id(sample_params):
    return sample_params["sample"]["node_tree"][0]["id"]


def dt(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)


def make_uuid():
    return uuid.uuid4()


def nw():
    return datetime.datetime.fromtimestamp(1, tz=datetime.timezone.utc)


def now_fun(now=None):
    if now is None:
        now = datetime.datetime.now(tz=datetime.timezone.utc)

    def now_funny():
        return now

    return now_funny


def sorted_dict(d):
    return dict(sorted(d.items()))
