import configparser
import os
import socket
import time
from contextlib import closing
from pathlib import Path

TEST_TEMP_DIR = "test.temp.dir"
KEEP_TEMP_DIR = "test.temp.dir.keep"
TEST_CONFIG_FILE_SECTION = "sampleservicetest"
TEST_FILE_LOC_ENV_KEY = "SAMPLESERV_TEST_FILE"
_CONFIG = None


def get_temp_dir() -> Path:
    return Path(os.path.abspath(_get_test_property(TEST_TEMP_DIR)))


def get_delete_temp_files() -> bool:
    return _get_test_property(KEEP_TEMP_DIR) != "true"


def _get_test_config_file_path() -> Path:
    p = os.environ.get(TEST_FILE_LOC_ENV_KEY)
    if not p:
        raise TestException(
            "Can't find key {} in environment".format(TEST_FILE_LOC_ENV_KEY)
        )
    return Path(p)


def _get_test_property(prop: str) -> str:
    global _CONFIG
    if not _CONFIG:
        test_cfg = _get_test_config_file_path()
        config = configparser.ConfigParser()
        config.read(test_cfg)
        if TEST_CONFIG_FILE_SECTION not in config:
            raise TestException(
                "No section {} found in test config file {}".format(
                    TEST_CONFIG_FILE_SECTION, test_cfg
                )
            )
        sec = config[TEST_CONFIG_FILE_SECTION]
        # a section is not a real map and is missing methods
        _CONFIG = {x: sec[x] for x in sec.keys()}
    if prop not in _CONFIG:
        test_cfg = _get_test_config_file_path()
        raise TestException(
            "Property {} in section {} of test file {} is missing".format(
                prop, TEST_CONFIG_FILE_SECTION, test_cfg
            )
        )
    return _CONFIG[prop]


def find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def assert_exception_correct(got: Exception, expected: Exception):
    assert got.args == expected.args
    assert type(got) == type(expected)


def assert_ms_epoch_close_to_now(some_time_ms, close_ms=1000):
    now_ms = time.time() * 1000
    assert now_ms + close_ms > some_time_ms
    assert now_ms - close_ms < some_time_ms


class TestException(Exception):
    __test__ = False
