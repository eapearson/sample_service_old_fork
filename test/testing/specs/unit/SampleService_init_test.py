from pytest import raises
from SampleService.core.errors import MissingParameterError
from SampleService.SampleServiceImpl import SampleService
from testing.shared.test_utils import assert_exception_correct


def init_fail(config, expected):
    with raises(Exception) as got:
        SampleService(config)
    assert_exception_correct(got.value, expected)


def test_init_fail():
    # init success is tested via starting the server
    init_fail(None, ValueError('config is empty, cannot start service'))
    cfg = {}
    init_fail(cfg, ValueError('config is empty, cannot start service'))
    cfg['arango-url'] = None
    init_fail(cfg, MissingParameterError('config param arango-url'))
    cfg['arango-url'] = 'crap'
    init_fail(cfg, MissingParameterError('config param arango-db'))
    cfg['arango-db'] = 'crap'
    init_fail(cfg, MissingParameterError('config param arango-user'))
    cfg['arango-user'] = 'crap'
    init_fail(cfg, MissingParameterError('config param arango-pwd'))
    cfg['arango-pwd'] = 'crap'
    init_fail(cfg, MissingParameterError('config param sample-collection'))
    cfg['sample-collection'] = 'crap'
    init_fail(cfg, MissingParameterError('config param version-collection'))
    cfg['version-collection'] = 'crap'
    init_fail(cfg, MissingParameterError('config param version-edge-collection'))
    cfg['version-edge-collection'] = 'crap'
    init_fail(cfg, MissingParameterError('config param node-collection'))
    cfg['node-collection'] = 'crap'
    init_fail(cfg, MissingParameterError('config param node-edge-collection'))
    cfg['node-edge-collection'] = 'crap'
    init_fail(cfg, MissingParameterError('config param data-link-collection'))
    cfg['data-link-collection'] = 'crap'
    init_fail(cfg, MissingParameterError(
        'config param workspace-object-version-shadow-collection'))
    cfg['workspace-object-version-shadow-collection'] = 'crap'
    init_fail(cfg, MissingParameterError('config param schema-collection'))
    cfg['schema-collection'] = 'crap'
    init_fail(cfg, MissingParameterError('config param auth-root-url'))
    cfg['auth-root-url'] = 'crap'
    init_fail(cfg, MissingParameterError('config param auth-token'))
    cfg['auth-token'] = 'crap'
    init_fail(cfg, MissingParameterError('config param workspace-url'))
    cfg['workspace-url'] = 'crap'
    init_fail(cfg, MissingParameterError('config param workspace-read-admin-token'))
    cfg['workspace-read-admin-token'] = 'crap'
    cfg['kafka-bootstrap-servers'] = 'crap'
    init_fail(cfg, MissingParameterError('config param kafka-topic'))
    cfg['kafka-topic'] = 'crap'
    # get_validators is tested elsewhere, just make sure it'll error out
    cfg['metadata-validator-config-url'] = 'https://kbase.us/services'
    init_fail(cfg, ValueError(
        'Failed to open validator configuration file at https://kbase.us/services: Not Found'))
