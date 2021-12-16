# ###########################
# Kafka notifier tests
# ###########################

from kafka.errors import NoBrokersAvailable
from pytest import raises
from SampleService.core.errors import (IllegalParameterError,
                                       MissingParameterError)
from SampleService.core.notification import KafkaNotifier
from testing.shared.test_utils import assert_exception_correct, find_free_port


def test_kafka_notifier_init_fail():
    def kafka_notifier_init_fail(servers, topic, expected):
        with raises(Exception) as got:
            KafkaNotifier(servers, topic)
        assert_exception_correct(got.value, expected)

    kafka_notifier_init_fail(None, 't', MissingParameterError('bootstrap_servers'))
    kafka_notifier_init_fail('   \t   ', 't', MissingParameterError('bootstrap_servers'))
    kafka_notifier_init_fail('localhost:10000', None, MissingParameterError('topic'))
    kafka_notifier_init_fail('localhost:10000', '   \t   ', MissingParameterError('topic'))
    kafka_notifier_init_fail(
        'localhost:10000', 'mytopic' + 243 * 'a',
        IllegalParameterError('topic exceeds maximum length of 249'))
    kafka_notifier_init_fail(f'localhost:{find_free_port()}', 'mytopic', NoBrokersAvailable())

    for c in ['Ѽ', '_', '.', '*']:
        kafka_notifier_init_fail('localhost:10000', f'topic{c}topic', ValueError(
            f'Illegal character in Kafka topic topic{c}topic: {c}'))
