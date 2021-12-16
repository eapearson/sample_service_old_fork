# ###########################
# Kafka notifier tests
# ###########################

# These tests cover the integration of the entire system and do not go into details - that's
# what unit tests are for. As such, typically each method will get a single happy path test and
# a single unhappy path test unless otherwise warranted.


import uuid

from pytest import raises
from SampleService.core.notification import KafkaNotifier
from testing.shared.common import check_kafka_messages
from testing.shared.test_utils import assert_exception_correct


def test_kafka_notifier_new_sample(kafka_host):
    topic = (
        "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-" + 186 * "a"
    )
    kn = KafkaNotifier(kafka_host, topic)
    try:
        sample_id = uuid.uuid4()

        kn.notify_new_sample_version(sample_id, 6)

        check_kafka_messages(
            kafka_host,
            [
                {
                    "event_type": "NEW_SAMPLE",
                    "sample_id": str(sample_id),
                    "sample_ver": 6,
                }
            ],
            topic,
        )
    finally:
        kn.close()


def test_kafka_notifier_notify_new_sample_version_fail(kafka_host):
    kn = KafkaNotifier(kafka_host, "mytopic")

    def kafka_notifier_notify_new_sample_version_fail(
        notifier, sample, version, expected
    ):
        with raises(Exception) as got:
            notifier.notify_new_sample_version(sample, version)
        assert_exception_correct(got.value, expected)

    kafka_notifier_notify_new_sample_version_fail(
        kn, None, 1, ValueError("sample_id cannot be a value that evaluates to false")
    )
    kafka_notifier_notify_new_sample_version_fail(
        kn, uuid.uuid4(), 0, ValueError("sample_ver must be > 0")
    )
    kafka_notifier_notify_new_sample_version_fail(
        kn, uuid.uuid4(), -3, ValueError("sample_ver must be > 0")
    )

    kn.close()
    kafka_notifier_notify_new_sample_version_fail(
        kn, uuid.uuid4(), 1, ValueError("client is closed")
    )


def test_kafka_notifier_acl_change(kafka_host):
    kn = KafkaNotifier(kafka_host, "topictopic")
    try:
        id_ = uuid.uuid4()

        kn.notify_sample_acl_change(id_)

        check_kafka_messages(
            kafka_host,
            [{"event_type": "ACL_CHANGE", "sample_id": str(id_)}],
            "topictopic",
        )
    finally:
        kn.close()


def test_kafka_notifier_notify_acl_change_fail(kafka_host):
    kn = KafkaNotifier(kafka_host, "mytopic")

    def kafka_notifier_notify_acl_change_fail(notifier, sample, expected):
        with raises(Exception) as got:
            notifier.notify_sample_acl_change(sample)
        assert_exception_correct(got.value, expected)

    kafka_notifier_notify_acl_change_fail(
        kn, None, ValueError("sample_id cannot be a value that evaluates to false")
    )

    kn.close()
    kafka_notifier_notify_acl_change_fail(
        kn, uuid.uuid4(), ValueError("client is closed")
    )


def test_kafka_notifier_new_link(kafka_host):
    kn = KafkaNotifier(kafka_host, "topictopic")
    try:
        id_ = uuid.uuid4()

        kn.notify_new_link(id_)

        check_kafka_messages(
            kafka_host, [{"event_type": "NEW_LINK", "link_id": str(id_)}], "topictopic"
        )
    finally:
        kn.close()


def test_kafka_notifier_new_link_fail(kafka_host):
    kn = KafkaNotifier(kafka_host, "mytopic")

    def kafka_notifier_new_link_fail(notifier, sample, expected):
        with raises(Exception) as got:
            notifier.notify_new_link(sample)
        assert_exception_correct(got.value, expected)

    kafka_notifier_new_link_fail(
        kn, None, ValueError("link_id cannot be a value that evaluates to false")
    )

    kn.close()
    kafka_notifier_new_link_fail(kn, uuid.uuid4(), ValueError("client is closed"))


def test_kafka_notifier_expired_link(kafka_host):
    kn = KafkaNotifier(kafka_host, "topictopic")
    try:
        id_ = uuid.uuid4()

        kn.notify_expired_link(id_)

        check_kafka_messages(
            kafka_host,
            [{"event_type": "EXPIRED_LINK", "link_id": str(id_)}],
            "topictopic",
        )
    finally:
        kn.close()


def test_kafka_notifier_expired_link_fail(kafka_host):
    kn = KafkaNotifier(kafka_host, "mytopic")

    def kafka_notifier_expired_link_fail(notifier, sample, expected):
        with raises(Exception) as got:
            notifier.notify_expired_link(sample)
        assert_exception_correct(got.value, expected)

    kafka_notifier_expired_link_fail(
        kn, None, ValueError("link_id cannot be a value that evaluates to false")
    )

    kn.close()
    kafka_notifier_expired_link_fail(kn, uuid.uuid4(), ValueError("client is closed"))
