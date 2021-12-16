import datetime
import uuid

from pytest import raises
from SampleService.core.data_link import DataLink
from SampleService.core.errors import (DataLinkExistsError, NoSuchLinkError,
                                       NoSuchSampleError,
                                       NoSuchSampleNodeError,
                                       NoSuchSampleVersionError,
                                       TooManyDataLinksError)
from SampleService.core.sample import (SampleAddress, SampleNode,
                                       SampleNodeAddress, SavedSample,
                                       SubSampleType)
from SampleService.core.storage.arango_sample_storage import \
    ArangoSampleStorage
from SampleService.core.storage.errors import SampleStorageError
from SampleService.core.user import UserID
from SampleService.core.workspace import UPA, DataUnitID
from testing.shared.common import (TEST_COL_DATA_LINK, TEST_COL_WS_OBJ_VER, dt,
                                   make_uuid)
from testing.shared.test_utils import assert_exception_correct

TEST_NODE = SampleNode('foo')


#
# Utilities
#


def _samplestorage_with_max_links(samplestorage, max_links):
    # this is very naughty
    return ArangoSampleStorage(
        samplestorage._db,
        samplestorage._col_sample.name,
        samplestorage._col_version.name,
        samplestorage._col_ver_edge.name,
        samplestorage._col_nodes.name,
        samplestorage._col_node_edge.name,
        samplestorage._col_ws.name,
        samplestorage._col_data_link.name,
        samplestorage._col_schema.name,
        max_links=max_links)


def _get_links_from_sample_fail(
        samplestorage, sample_address, wsids, timestamp, expected):
    with raises(Exception) as got:
        samplestorage.get_links_from_sample(sample_address, wsids, timestamp)
    assert_exception_correct(got.value, expected)


def _create_data_link_fail(samplestorage, link, expected, update=False):
    with raises(Exception) as got:
        samplestorage.create_data_link(link, update)
    assert_exception_correct(got.value, expected)


def _create_and_expire_data_link(samplestorage, link, expired, user):
    samplestorage.create_data_link(link)
    samplestorage.expire_data_link(expired, user, link.id)


def _get_data_link_fail(samplestorage, id_, duid, expected):
    with raises(Exception) as got:
        samplestorage.get_data_link(id_, duid)
    assert_exception_correct(got.value, expected)


def _expire_and_get_data_link_via_duid(samplestorage, expired, dataid, expectedmd5):
    sid = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(sid, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    lid = uuid.UUID('1234567890abcdef1234567890abcde1')
    samplestorage.create_data_link(DataLink(
        lid,
        DataUnitID(UPA('1/1/1'), dataid),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(-100),
        UserID('userb'))
    )

    # this is naughty
    verdoc1 = samplestorage._col_version.find({'id': str(sid), 'ver': 1}).next()
    nodedoc1 = samplestorage._col_nodes.find({'name': 'mynode'}).next()

    assert samplestorage.expire_data_link(
        dt(expired), UserID('yay'), duid=DataUnitID(UPA('1/1/1'), dataid)) == DataLink(
        lid,
        DataUnitID(UPA('1/1/1'), dataid),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(-100),
        UserID('userb'),
        dt(expired),
        UserID('yay')
    )

    assert samplestorage._col_data_link.count() == 1

    link = samplestorage._col_data_link.get(f'1_1_1_{expectedmd5}-100.0')
    assert link == {
        '_key': f'1_1_1_{expectedmd5}-100.0',
        '_id': f'{TEST_COL_DATA_LINK}/1_1_1_{expectedmd5}-100.0',
        '_from': f'{TEST_COL_WS_OBJ_VER}/1:1:1',
        '_to': nodedoc1['_id'],
        '_rev': link['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde1',
        'wsid': 1,
        'objid': 1,
        'objver': 1,
        'dataid': dataid,
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc1['uuidver'],
        'samintver': 1,
        'node': 'mynode',
        'created': -100000,
        'createby': 'userb',
        'expired': expired * 1000,
        'expireby': 'yay'
    }

    assert samplestorage.get_data_link(lid) == DataLink(
        lid,
        DataUnitID(UPA('1/1/1'), dataid),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(-100),
        UserID('userb'),
        dt(expired),
        UserID('yay')
    )


def _expire_and_get_data_link_via_id(samplestorage, expired, dataid, expectedmd5):
    sid = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(sid, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    lid = uuid.UUID('1234567890abcdef1234567890abcde1')
    samplestorage.create_data_link(DataLink(
        lid,
        DataUnitID(UPA('1/1/1'), dataid),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(5),
        UserID('usera'))
    )

    # this is naughty
    verdoc1 = samplestorage._col_version.find({'id': str(sid), 'ver': 1}).next()
    nodedoc1 = samplestorage._col_nodes.find({'name': 'mynode'}).next()

    assert samplestorage.expire_data_link(dt(expired), UserID('user'), id_=lid) == DataLink(
        lid,
        DataUnitID(UPA('1/1/1'), dataid),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(5),
        UserID('usera'),
        dt(expired),
        UserID('user')
    )

    assert samplestorage._col_data_link.count() == 1

    link = samplestorage._col_data_link.get(f'1_1_1_{expectedmd5}5.0')
    assert link == {
        '_key': f'1_1_1_{expectedmd5}5.0',
        '_id': f'{TEST_COL_DATA_LINK}/1_1_1_{expectedmd5}5.0',
        '_from': f'{TEST_COL_WS_OBJ_VER}/1:1:1',
        '_to': nodedoc1['_id'],
        '_rev': link['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde1',
        'wsid': 1,
        'objid': 1,
        'objver': 1,
        'dataid': dataid,
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc1['uuidver'],
        'samintver': 1,
        'node': 'mynode',
        'created': 5000,
        'createby': 'usera',
        'expired': expired * 1000,
        'expireby': 'user'
    }

    link = samplestorage.get_data_link(lid)
    expected = DataLink(
        lid,
        DataUnitID(UPA('1/1/1'), dataid),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(5),
        UserID('usera'),
        dt(expired),
        UserID('user')
    )
    assert link == expected


def _expire_data_link_fail(samplestorage, expire, user, id_, duid, expected):
    with raises(Exception) as got:
        samplestorage.expire_data_link(expire, user, id_, duid)
    assert_exception_correct(got.value, expected)


#
# Testing
#


def test_create_and_get_data_link(samplestorage):
    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    id2 = uuid.UUID('1234567890abcdef1234567890abcdee')
    assert samplestorage.save_sample(
        SavedSample(id1, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True
    assert samplestorage.save_sample_version(
        SavedSample(id1, UserID('user'), [SampleNode('mynode1')], dt(2), 'foo')) == 2
    assert samplestorage.save_sample(
        SavedSample(id2, UserID('user'), [SampleNode('mynode2')], dt(3), 'foo')) is True

    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde1'),
        DataUnitID(UPA('5/89/32')),
        SampleNodeAddress(SampleAddress(id1, 2), 'mynode1'),
        dt(500),
        UserID('usera'))
    ) is None

    # test different workspace object and different sample version
    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde2'),
        DataUnitID(UPA('42/42/42'), 'dataunit1'),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(600),
        UserID('userb'))
    ) is None

    # test data unit vs just UPA, different sample, and expiration date
    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde3'),
        DataUnitID(UPA('5/89/32'), 'dataunit2'),
        SampleNodeAddress(SampleAddress(id2, 1), 'mynode2'),
        dt(700),
        UserID('u'))
    ) is None

    # test data units don't collide if they have different names
    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde4'),
        DataUnitID(UPA('5/89/32'), 'dataunit1'),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(800),
        UserID('userd'))
    ) is None

    # this is naughty
    verdoc1 = samplestorage._col_version.find({'id': str(id1), 'ver': 1}).next()
    verdoc2 = samplestorage._col_version.find({'id': str(id1), 'ver': 2}).next()
    verdoc3 = samplestorage._col_version.find({'id': str(id2), 'ver': 1}).next()
    nodedoc1 = samplestorage._col_nodes.find({'name': 'mynode'}).next()
    nodedoc2 = samplestorage._col_nodes.find({'name': 'mynode1'}).next()
    nodedoc3 = samplestorage._col_nodes.find({'name': 'mynode2'}).next()

    assert samplestorage._col_data_link.count() == 4

    # check arango documents correct, particularly _* values
    link1 = samplestorage._col_data_link.get('5_89_32')
    assert link1 == {
        '_key': '5_89_32',
        '_id': f'{TEST_COL_DATA_LINK}/5_89_32',
        '_from': f'{TEST_COL_WS_OBJ_VER}/5:89:32',
        '_to': nodedoc2['_id'],
        '_rev': link1['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde1',
        'wsid': 5,
        'objid': 89,
        'objver': 32,
        'dataid': None,
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc2['uuidver'],
        'samintver': 2,
        'node': 'mynode1',
        'created': 500000,
        'createby': 'usera',
        'expired': 9007199254740991,
        'expireby': None
    }

    link2 = samplestorage._col_data_link.get('42_42_42_bc7324de86d54718dd0dc29c55c6d53a')
    assert link2 == {
        '_key': '42_42_42_bc7324de86d54718dd0dc29c55c6d53a',
        '_id': f'{TEST_COL_DATA_LINK}/42_42_42_bc7324de86d54718dd0dc29c55c6d53a',
        '_from': f'{TEST_COL_WS_OBJ_VER}/42:42:42',
        '_to': nodedoc1['_id'],
        '_rev': link2['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde2',
        'wsid': 42,
        'objid': 42,
        'objver': 42,
        'dataid': 'dataunit1',
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc1['uuidver'],
        'samintver': 1,
        'node': 'mynode',
        'created': 600000,
        'createby': 'userb',
        'expired': 9007199254740991,
        'expireby': None
    }

    link3 = samplestorage._col_data_link.get('5_89_32_3735ce9bbe59e7ec245da484772f9524')
    assert link3 == {
        '_key': '5_89_32_3735ce9bbe59e7ec245da484772f9524',
        '_id': f'{TEST_COL_DATA_LINK}/5_89_32_3735ce9bbe59e7ec245da484772f9524',
        '_from': f'{TEST_COL_WS_OBJ_VER}/5:89:32',
        '_to': nodedoc3['_id'],
        '_rev': link3['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde3',
        'wsid': 5,
        'objid': 89,
        'objver': 32,
        'dataid': 'dataunit2',
        'sampleid': '12345678-90ab-cdef-1234-567890abcdee',
        'samuuidver': verdoc3['uuidver'],
        'samintver': 1,
        'node': 'mynode2',
        'created': 700000,
        'createby': 'u',
        'expired': 9007199254740991,
        'expireby': None
    }

    link4 = samplestorage._col_data_link.get('5_89_32_bc7324de86d54718dd0dc29c55c6d53a')
    assert link4 == {
        '_key': '5_89_32_bc7324de86d54718dd0dc29c55c6d53a',
        '_id': f'{TEST_COL_DATA_LINK}/5_89_32_bc7324de86d54718dd0dc29c55c6d53a',
        '_from': f'{TEST_COL_WS_OBJ_VER}/5:89:32',
        '_to': nodedoc1['_id'],
        '_rev': link4['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde4',
        'wsid': 5,
        'objid': 89,
        'objver': 32,
        'dataid': 'dataunit1',
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc1['uuidver'],
        'samintver': 1,
        'node': 'mynode',
        'created': 800000,
        'createby': 'userd',
        'expired': 9007199254740991,
        'expireby': None
    }

    # test get method
    dl1 = samplestorage.get_data_link(uuid.UUID('12345678-90ab-cdef-1234-567890abcde1'))
    assert dl1 == DataLink(
        uuid.UUID('12345678-90ab-cdef-1234-567890abcde1'),
        DataUnitID(UPA('5/89/32')),
        SampleNodeAddress(
            SampleAddress(uuid.UUID('12345678-90ab-cdef-1234-567890abcdef'), 2),
            'mynode1'),
        dt(500),
        UserID('usera')
    )

    dl2 = samplestorage.get_data_link(duid=DataUnitID(UPA('42/42/42'), 'dataunit1'))
    assert dl2 == DataLink(
        uuid.UUID('12345678-90ab-cdef-1234-567890abcde2'),
        DataUnitID(UPA('42/42/42'), 'dataunit1'),
        SampleNodeAddress(
            SampleAddress(uuid.UUID('12345678-90ab-cdef-1234-567890abcdef'), 1),
            'mynode'),
        dt(600),
        UserID('userb')
    )

    dl3 = samplestorage.get_data_link(duid=DataUnitID(UPA('5/89/32'), 'dataunit2'))
    assert dl3 == DataLink(
        uuid.UUID('12345678-90ab-cdef-1234-567890abcde3'),
        DataUnitID(UPA('5/89/32'), 'dataunit2'),
        SampleNodeAddress(
            SampleAddress(uuid.UUID('12345678-90ab-cdef-1234-567890abcdee'), 1),
            'mynode2'),
        dt(700),
        UserID('u')
    )

    dl4 = samplestorage.get_data_link(id_=uuid.UUID('12345678-90ab-cdef-1234-567890abcde4'))
    assert dl4 == DataLink(
        uuid.UUID('12345678-90ab-cdef-1234-567890abcde4'),
        DataUnitID(UPA('5/89/32'), 'dataunit1'),
        SampleNodeAddress(
            SampleAddress(uuid.UUID('12345678-90ab-cdef-1234-567890abcdef'), 1),
            'mynode'),
        dt(800),
        UserID('userd')
    )


def test_creaate_data_link_with_update_no_extant_link(samplestorage):
    """
    Tests the case where an update is requested but is not necessary.
    """
    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(SavedSample(
        id1, UserID('user'), [SampleNode('mynode'), SampleNode('mynode1')], dt(1), 'foo')) is True

    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde1'),
        DataUnitID(UPA('5/89/32')),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(500),
        UserID('usera')),
        update=True
    ) is None

    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde2'),
        DataUnitID(UPA('5/89/32'), 'dataunit1'),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode1'),
        dt(550),
        UserID('user')),
        update=True
    ) is None

    # this is naughty
    verdoc1 = samplestorage._col_version.find({'id': str(id1), 'ver': 1}).next()
    nodedoc1 = samplestorage._col_nodes.find({'name': 'mynode'}).next()
    nodedoc2 = samplestorage._col_nodes.find({'name': 'mynode1'}).next()

    assert samplestorage._col_data_link.count() == 2

    # check arango documents correct, particularly _* values
    link1 = samplestorage._col_data_link.get('5_89_32')
    assert link1 == {
        '_key': '5_89_32',
        '_id': f'{TEST_COL_DATA_LINK}/5_89_32',
        '_from': f'{TEST_COL_WS_OBJ_VER}/5:89:32',
        '_to': nodedoc1['_id'],
        '_rev': link1['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde1',
        'wsid': 5,
        'objid': 89,
        'objver': 32,
        'dataid': None,
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc1['uuidver'],
        'samintver': 1,
        'node': 'mynode',
        'created': 500000,
        'createby': 'usera',
        'expired': 9007199254740991,
        'expireby': None
    }

    link2 = samplestorage._col_data_link.get('5_89_32_bc7324de86d54718dd0dc29c55c6d53a')
    assert link2 == {
        '_key': '5_89_32_bc7324de86d54718dd0dc29c55c6d53a',
        '_id': f'{TEST_COL_DATA_LINK}/5_89_32_bc7324de86d54718dd0dc29c55c6d53a',
        '_from': f'{TEST_COL_WS_OBJ_VER}/5:89:32',
        '_to': nodedoc2['_id'],
        '_rev': link2['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde2',
        'wsid': 5,
        'objid': 89,
        'objver': 32,
        'dataid': 'dataunit1',
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc1['uuidver'],
        'samintver': 1,
        'node': 'mynode1',
        'created': 550000,
        'createby': 'user',
        'expired': 9007199254740991,
        'expireby': None
    }

    # test get method
    dl1 = samplestorage.get_data_link(uuid.UUID('12345678-90ab-cdef-1234-567890abcde1'))
    assert dl1 == DataLink(
        uuid.UUID('12345678-90ab-cdef-1234-567890abcde1'),
        DataUnitID(UPA('5/89/32')),
        SampleNodeAddress(
            SampleAddress(uuid.UUID('12345678-90ab-cdef-1234-567890abcdef'), 1),
            'mynode'),
        dt(500),
        UserID('usera')
    )

    dl2 = samplestorage.get_data_link(uuid.UUID('12345678-90ab-cdef-1234-567890abcde2'))
    assert dl2 == DataLink(
        uuid.UUID('12345678-90ab-cdef-1234-567890abcde2'),
        DataUnitID(UPA('5/89/32'), 'dataunit1'),
        SampleNodeAddress(
            SampleAddress(uuid.UUID('12345678-90ab-cdef-1234-567890abcdef'), 1),
            'mynode1'),
        dt(550),
        UserID('user')
    )


def test_create_data_link_with_update_noop(samplestorage):
    """
    Tests the case where a link update is requested but an equivalent link already exists.
    """
    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(SavedSample(
        id1, UserID('user'), [SampleNode('mynode'), SampleNode('mynode1')], dt(1), 'foo')) is True

    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde1'),
        DataUnitID(UPA('5/89/32')),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(500),
        UserID('usera'))
    ) is None

    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde2'),
        DataUnitID(UPA('5/89/32'), 'dataunit1'),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode1'),
        dt(550),
        UserID('user'))
    ) is None

    # expect noop
    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde3'),
        DataUnitID(UPA('5/89/32')),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(600),
        UserID('userb')),
        update=True
    ) is None

    # expect noop
    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde4'),
        DataUnitID(UPA('5/89/32'), 'dataunit1'),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode1'),
        dt(700),
        UserID('userc')),
        update=True
    ) is None

    # this is naughty
    verdoc1 = samplestorage._col_version.find({'id': str(id1), 'ver': 1}).next()
    nodedoc1 = samplestorage._col_nodes.find({'name': 'mynode'}).next()
    nodedoc2 = samplestorage._col_nodes.find({'name': 'mynode1'}).next()

    assert samplestorage._col_data_link.count() == 2

    # check arango documents correct, particularly _* values
    link1 = samplestorage._col_data_link.get('5_89_32')
    assert link1 == {
        '_key': '5_89_32',
        '_id': f'{TEST_COL_DATA_LINK}/5_89_32',
        '_from': f'{TEST_COL_WS_OBJ_VER}/5:89:32',
        '_to': nodedoc1['_id'],
        '_rev': link1['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde1',
        'wsid': 5,
        'objid': 89,
        'objver': 32,
        'dataid': None,
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc1['uuidver'],
        'samintver': 1,
        'node': 'mynode',
        'created': 500000,
        'createby': 'usera',
        'expired': 9007199254740991,
        'expireby': None
    }

    link2 = samplestorage._col_data_link.get('5_89_32_bc7324de86d54718dd0dc29c55c6d53a')
    assert link2 == {
        '_key': '5_89_32_bc7324de86d54718dd0dc29c55c6d53a',
        '_id': f'{TEST_COL_DATA_LINK}/5_89_32_bc7324de86d54718dd0dc29c55c6d53a',
        '_from': f'{TEST_COL_WS_OBJ_VER}/5:89:32',
        '_to': nodedoc2['_id'],
        '_rev': link2['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde2',
        'wsid': 5,
        'objid': 89,
        'objver': 32,
        'dataid': 'dataunit1',
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc1['uuidver'],
        'samintver': 1,
        'node': 'mynode1',
        'created': 550000,
        'createby': 'user',
        'expired': 9007199254740991,
        'expireby': None
    }

    # test get method
    dl1 = samplestorage.get_data_link(uuid.UUID('12345678-90ab-cdef-1234-567890abcde1'))
    assert dl1 == DataLink(
        uuid.UUID('12345678-90ab-cdef-1234-567890abcde1'),
        DataUnitID(UPA('5/89/32')),
        SampleNodeAddress(
            SampleAddress(uuid.UUID('12345678-90ab-cdef-1234-567890abcdef'), 1),
            'mynode'),
        dt(500),
        UserID('usera')
    )

    dl2 = samplestorage.get_data_link(uuid.UUID('12345678-90ab-cdef-1234-567890abcde2'))
    assert dl2 == DataLink(
        uuid.UUID('12345678-90ab-cdef-1234-567890abcde2'),
        DataUnitID(UPA('5/89/32'), 'dataunit1'),
        SampleNodeAddress(
            SampleAddress(uuid.UUID('12345678-90ab-cdef-1234-567890abcdef'), 1),
            'mynode1'),
        dt(550),
        UserID('user')
    )


def test_create_data_link_with_update(samplestorage):
    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(SavedSample(
        id1, UserID('user'), [SampleNode('mynode'), SampleNode('mynode1'), SampleNode('mynode2')],
        dt(1), 'foo')) is True

    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde1'),
        DataUnitID(UPA('5/89/32')),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(500),
        UserID('usera'))
    ) is None

    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde2'),
        DataUnitID(UPA('5/89/32'), 'dataunit1'),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode1'),
        dt(550),
        UserID('user'))
    ) is None

    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde3'),
        DataUnitID(UPA('5/89/32')),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode1'),  # update the node
        dt(600),
        UserID('userb')),
        update=True
    ) == uuid.UUID('1234567890abcdef1234567890abcde1')

    assert samplestorage.create_data_link(DataLink(
        uuid.UUID('1234567890abcdef1234567890abcde4'),
        DataUnitID(UPA('5/89/32'), 'dataunit1'),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode2'),  # update the node
        dt(700),
        UserID('userc')),
        update=True
    ) == uuid.UUID('1234567890abcdef1234567890abcde2')

    # this is naughty
    verdoc1 = samplestorage._col_version.find({'id': str(id1), 'ver': 1}).next()
    nodedoc1 = samplestorage._col_nodes.find({'name': 'mynode'}).next()
    nodedoc2 = samplestorage._col_nodes.find({'name': 'mynode1'}).next()
    nodedoc3 = samplestorage._col_nodes.find({'name': 'mynode2'}).next()

    assert samplestorage._col_data_link.count() == 4

    # check arango documents correct, particularly _* values
    link1 = samplestorage._col_data_link.get('5_89_32_500.0')
    assert link1 == {
        '_key': '5_89_32_500.0',
        '_id': f'{TEST_COL_DATA_LINK}/5_89_32_500.0',
        '_from': f'{TEST_COL_WS_OBJ_VER}/5:89:32',
        '_to': nodedoc1['_id'],
        '_rev': link1['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde1',
        'wsid': 5,
        'objid': 89,
        'objver': 32,
        'dataid': None,
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc1['uuidver'],
        'samintver': 1,
        'node': 'mynode',
        'created': 500000,
        'createby': 'usera',
        'expired': 599999,
        'expireby': 'userb'
    }

    link2 = samplestorage._col_data_link.get('5_89_32_bc7324de86d54718dd0dc29c55c6d53a_550.0')
    assert link2 == {
        '_key': '5_89_32_bc7324de86d54718dd0dc29c55c6d53a_550.0',
        '_id': f'{TEST_COL_DATA_LINK}/5_89_32_bc7324de86d54718dd0dc29c55c6d53a_550.0',
        '_from': f'{TEST_COL_WS_OBJ_VER}/5:89:32',
        '_to': nodedoc2['_id'],
        '_rev': link2['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde2',
        'wsid': 5,
        'objid': 89,
        'objver': 32,
        'dataid': 'dataunit1',
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc1['uuidver'],
        'samintver': 1,
        'node': 'mynode1',
        'created': 550000,
        'createby': 'user',
        'expired': 699999,
        'expireby': 'userc'
    }

    link3 = samplestorage._col_data_link.get('5_89_32')
    assert link3 == {
        '_key': '5_89_32',
        '_id': f'{TEST_COL_DATA_LINK}/5_89_32',
        '_from': f'{TEST_COL_WS_OBJ_VER}/5:89:32',
        '_to': nodedoc2['_id'],
        '_rev': link3['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde3',
        'wsid': 5,
        'objid': 89,
        'objver': 32,
        'dataid': None,
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc1['uuidver'],
        'samintver': 1,
        'node': 'mynode1',
        'created': 600000,
        'createby': 'userb',
        'expired': 9007199254740991,
        'expireby': None
    }

    link4 = samplestorage._col_data_link.get('5_89_32_bc7324de86d54718dd0dc29c55c6d53a')
    assert link4 == {
        '_key': '5_89_32_bc7324de86d54718dd0dc29c55c6d53a',
        '_id': f'{TEST_COL_DATA_LINK}/5_89_32_bc7324de86d54718dd0dc29c55c6d53a',
        '_from': f'{TEST_COL_WS_OBJ_VER}/5:89:32',
        '_to': nodedoc3['_id'],
        '_rev': link4['_rev'],  # no need to test this
        'id': '12345678-90ab-cdef-1234-567890abcde4',
        'wsid': 5,
        'objid': 89,
        'objver': 32,
        'dataid': 'dataunit1',
        'sampleid': '12345678-90ab-cdef-1234-567890abcdef',
        'samuuidver': verdoc1['uuidver'],
        'samintver': 1,
        'node': 'mynode2',
        'created': 700000,
        'createby': 'userc',
        'expired': 9007199254740991,
        'expireby': None
    }

    # test get method. Expired, so DUID won't work here
    dl1 = samplestorage.get_data_link(uuid.UUID('12345678-90ab-cdef-1234-567890abcde1'))
    assert dl1 == DataLink(
        uuid.UUID('12345678-90ab-cdef-1234-567890abcde1'),
        DataUnitID(UPA('5/89/32')),
        SampleNodeAddress(
            SampleAddress(uuid.UUID('12345678-90ab-cdef-1234-567890abcdef'), 1), 'mynode'),
        dt(500),
        UserID('usera'),
        dt(599.999),
        UserID('userb')
    )

    dl2 = samplestorage.get_data_link(uuid.UUID('12345678-90ab-cdef-1234-567890abcde2'))
    assert dl2 == DataLink(
        uuid.UUID('12345678-90ab-cdef-1234-567890abcde2'),
        DataUnitID(UPA('5/89/32'), 'dataunit1'),
        SampleNodeAddress(
            SampleAddress(uuid.UUID('12345678-90ab-cdef-1234-567890abcdef'), 1), 'mynode1'),
        dt(550),
        UserID('user'),
        dt(699.999),
        UserID('userc')
    )

    dl3 = samplestorage.get_data_link(duid=DataUnitID(UPA('5/89/32')))
    assert dl3 == DataLink(
        uuid.UUID('12345678-90ab-cdef-1234-567890abcde3'),
        DataUnitID(UPA('5/89/32')),
        SampleNodeAddress(
            SampleAddress(uuid.UUID('12345678-90ab-cdef-1234-567890abcdef'), 1), 'mynode1'),
        dt(600),
        UserID('userb')
    )

    dl3 = samplestorage.get_data_link(uuid.UUID('12345678-90ab-cdef-1234-567890abcde4'))
    assert dl3 == DataLink(
        uuid.UUID('12345678-90ab-cdef-1234-567890abcde4'),
        DataUnitID(UPA('5/89/32'), 'dataunit1'),
        SampleNodeAddress(
            SampleAddress(uuid.UUID('12345678-90ab-cdef-1234-567890abcdef'), 1), 'mynode2'),
        dt(700),
        UserID('userc'),
    )


def test_create_data_link_correct_missing_versions(samplestorage):
    """
    Checks that the version correction code runs when needed on creating a data link.
    Since the method is tested extensively in the get_sample tests, we only run one test here
    to ensure the method is called.
    This test simulates a server coming up after a dirty shutdown, where version and
    node doc integer versions have not been updated
    """
    n1 = SampleNode('root')
    n2 = SampleNode('kid1', SubSampleType.TECHNICAL_REPLICATE, 'root')
    n3 = SampleNode('kid2', SubSampleType.SUB_SAMPLE, 'kid1')
    n4 = SampleNode('kid3', SubSampleType.TECHNICAL_REPLICATE, 'root')

    id_ = uuid.UUID('1234567890abcdef1234567890abcdef')

    assert samplestorage.save_sample(
        SavedSample(id_, UserID('user'), [n1, n2, n3, n4], dt(1), 'foo')) is True

    # this is very naughty
    # checked that these modifications actually work by viewing the db contents
    samplestorage._col_version.update_match({}, {'ver': -1})
    samplestorage._col_nodes.update_match({'name': 'kid2'}, {'ver': -1})

    assert samplestorage.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('5/89/32')),
        SampleNodeAddress(SampleAddress(id_, 1), 'kid1'),
        dt(500),
        UserID('user'))
    ) is None

    assert samplestorage._col_version.count() == 1
    assert samplestorage._col_ver_edge.count() == 1
    assert samplestorage._col_nodes.count() == 4
    assert samplestorage._col_node_edge.count() == 4

    for v in samplestorage._col_version.all():
        assert v['ver'] == 1

    for v in samplestorage._col_nodes.all():
        assert v['ver'] == 1


def test_create_data_link_fail_no_link(samplestorage):
    _create_data_link_fail(samplestorage, None, ValueError(
        'link cannot be a value that evaluates to false'))


def test_create_data_link_fail_expired(samplestorage):
    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(id1, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    _create_data_link_fail(
        samplestorage,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1')),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
            dt(-100),
            UserID('user'),
            dt(0),
            UserID('user')),
        ValueError('link cannot be expired')
    )


def test_create_data_link_fail_no_sample(samplestorage):
    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    id2 = uuid.UUID('1234567890abcdef1234567890abcdee')
    assert samplestorage.save_sample(
        SavedSample(id1, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    _create_data_link_fail(
        samplestorage,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1')),
            SampleNodeAddress(SampleAddress(id2, 1), 'mynode'),
            dt(1),
            UserID('user')),
        NoSuchSampleError(str(id2))
    )


def test_create_data_link_fail_no_sample_version(samplestorage):
    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(id1, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True
    assert samplestorage.save_sample_version(
        SavedSample(id1, UserID('user'), [SampleNode('mynode1')], dt(2), 'foo')) == 2

    _create_data_link_fail(
        samplestorage,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1')),
            SampleNodeAddress(SampleAddress(id1, 3), 'mynode'),
            dt(1),
            UserID('user')),
        NoSuchSampleVersionError('12345678-90ab-cdef-1234-567890abcdef ver 3')
    )


def test_create_data_link_fail_no_sample_node(samplestorage):
    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(SavedSample(
        id1, UserID('user'), [SampleNode('mynode'), SampleNode('mynode1')], dt(1), 'foo')) is True

    _create_data_link_fail(
        samplestorage,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1')),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode2'),
            dt(1),
            UserID('user')),
        NoSuchSampleNodeError('12345678-90ab-cdef-1234-567890abcdef ver 1 mynode2')
    )


def test_create_data_link_fail_link_exists(samplestorage):
    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(id1, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    samplestorage.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(500),
        UserID('user'))
    )

    samplestorage.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1'), 'du1'),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(500),
        UserID('user'))
    )

    _create_data_link_fail(
        samplestorage,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1')),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
            dt(1),
            UserID('user')),
        DataLinkExistsError('1/1/1')
    )

    _create_data_link_fail(
        samplestorage,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1'), 'du1'),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
            dt(1),
            UserID('user')),
        DataLinkExistsError('1/1/1:du1')
    )


def test_create_data_link_fail_too_many_links_from_ws_obj_basic(samplestorage):
    ss = _samplestorage_with_max_links(samplestorage, 3)

    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    id2 = uuid.UUID('1234567890abcdef1234567890abcde3')
    assert ss.save_sample(
        SavedSample(id1, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True
    assert ss.save_sample(
        SavedSample(id2, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    ss.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(500),
        UserID('user'))
    )

    ss.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1'), '1'),
        SampleNodeAddress(SampleAddress(id2, 1), 'mynode'),
        dt(500),
        UserID('user'))
    )

    ss.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1'), '2'),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(500),
        UserID('user'))
    )

    _create_data_link_fail(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1'), '3'),
            SampleNodeAddress(SampleAddress(id2, 1), 'mynode'),
            dt(1),
            UserID('user')),
        TooManyDataLinksError('More than 3 links from workspace object 1/1/1')
    )


def test_create_data_link_fail_too_many_links_from_sample_ver_basic(samplestorage):
    ss = _samplestorage_with_max_links(samplestorage, 2)

    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert ss.save_sample(SavedSample(
        id1, UserID('user'), [SampleNode('mynode'), SampleNode('mynode2')], dt(1), 'foo')) is True

    ss.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(500),
        UserID('user'))
    )

    ss.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/2')),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode2'),
        dt(500),
        UserID('user'))
    )

    _create_data_link_fail(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/3')),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
            dt(1),
            UserID('user')),
        TooManyDataLinksError(
            'More than 2 links from sample 12345678-90ab-cdef-1234-567890abcdef version 1')
    )


def test_create_data_link_fail_too_many_links_from_ws_obj_time_travel(samplestorage):
    # tests that links that do not co-exist with the new link are not counted against the total.
    ss = _samplestorage_with_max_links(samplestorage, 3)

    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert ss.save_sample(
        SavedSample(id1, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True
    assert ss.save_sample_version(
        SavedSample(id1, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) == 2

    # completely outside the new sample time range.
    _create_and_expire_data_link(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1')),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
            dt(100),
            UserID('user')),
        dt(299),
        UserID('user')
    )

    # expire matches create
    _create_and_expire_data_link(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1'), '1'),
            SampleNodeAddress(SampleAddress(id1, 2), 'mynode'),
            dt(100),
            UserID('user')),
        dt(300),
        UserID('user')
    )

    # overlaps create
    _create_and_expire_data_link(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1'), '2'),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
            dt(250),
            UserID('user')),
        dt(350),
        UserID('user')
    )

    # contained inside
    _create_and_expire_data_link(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1'), '3'),
            SampleNodeAddress(SampleAddress(id1, 2), 'mynode'),
            dt(325),
            UserID('user')),
        dt(375),
        UserID('user')
    )

    _create_data_link_fail(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1'), '8'),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
            dt(300),
            UserID('user')),
        TooManyDataLinksError('More than 3 links from workspace object 1/1/1')
    )


def test_create_data_link_fail_too_many_links_from_sample_ver_time_travel(samplestorage):
    # tests that links that do not co-exist with the new link are not counted against the total.
    ss = _samplestorage_with_max_links(samplestorage, 3)

    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert ss.save_sample(
        SavedSample(id1, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    # completely outside the new sample time range.
    _create_and_expire_data_link(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1')),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
            dt(100),
            UserID('user')),
        dt(299),
        UserID('user')
    )

    # expire matches create
    _create_and_expire_data_link(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/2')),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
            dt(100),
            UserID('user')),
        dt(300),
        UserID('user')
    )

    # overlaps create
    _create_and_expire_data_link(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/3')),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
            dt(250),
            UserID('user')),
        dt(350),
        UserID('user')
    )

    # contained inside
    _create_and_expire_data_link(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/4')),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
            dt(325),
            UserID('user')),
        dt(375),
        UserID('user')
    )

    _create_data_link_fail(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/9')),
            SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
            dt(300),
            UserID('user')),
        TooManyDataLinksError('More than 3 links from sample ' +
                              '12345678-90ab-cdef-1234-567890abcdef version 1')
    )


def test_create_data_link_update_links_from_ws_object_count_limit(samplestorage):
    """
    Tests that replacing a link doesn't trigger the link count limit from ws objects when
    it's at the max
    """
    ss = _samplestorage_with_max_links(samplestorage, 2)

    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    id2 = uuid.UUID('1234567890abcdef1234567890abcde3')
    assert ss.save_sample(
        SavedSample(id1, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True
    assert ss.save_sample(
        SavedSample(id2, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    ss.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(500),
        UserID('user'))
    )

    ss.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1'), '1'),
        SampleNodeAddress(SampleAddress(id2, 1), 'mynode'),
        dt(500),
        UserID('user'))
    )

    # should pass. Changing the data ID causes a fail
    ss.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1'), '1'),
        SampleNodeAddress(SampleAddress(id2, 1), 'mynode'),
        dt(500),
        UserID('user')),
        update=True
    )

    _create_data_link_fail(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1'), '2'),
            SampleNodeAddress(SampleAddress(id2, 1), 'mynode'),
            dt(500),
            UserID('user')),
        TooManyDataLinksError('More than 2 links from workspace object 1/1/1')
    )


def test_create_data_link_update_links_from_sample_ver_count_limit(samplestorage):
    """
    Tests updating a link with regard to the limit on number of links to a sample version.
    Specifically, updating a link to a different node of the same sample version should not
    cause an error, while violating the limit for a new sample version should cause an error.
    """
    ss = _samplestorage_with_max_links(samplestorage, 1)

    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    id2 = uuid.UUID('1234567890abcdef1234567890abcdee')
    assert samplestorage.save_sample(SavedSample(
        id1, UserID('user'), [SampleNode('mynode'), SampleNode('XmynodeX')], dt(1), 'foo')) is True
    assert samplestorage.save_sample_version(
        SavedSample(id1, UserID('user'), [SampleNode('mynode1')], dt(2), 'foo')) == 2
    assert samplestorage.save_sample(
        SavedSample(id2, UserID('user'), [SampleNode('mynode2')], dt(3), 'foo')) is True

    ss.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(id1, 1), 'mynode'),
        dt(500),
        UserID('user'))
    )

    ss.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/2')),
        SampleNodeAddress(SampleAddress(id1, 2), 'mynode1'),
        dt(500),
        UserID('user'))
    )

    ss.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/3')),
        SampleNodeAddress(SampleAddress(id2, 1), 'mynode2'),
        dt(500),
        UserID('user'))
    )

    # Should not trigger an error - replacing a link to the same sample version.
    ss.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(id1, 1), 'XmynodeX'),
        dt(600),
        UserID('user')),
        update=True
    )

    # fail on version change
    _create_data_link_fail(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1')),
            SampleNodeAddress(SampleAddress(id1, 2), 'mynode1'),
            dt(700),
            UserID('user')),
        TooManyDataLinksError(
            'More than 1 links from sample 12345678-90ab-cdef-1234-567890abcdef version 2'),
        update=True
    )

    # fail on sample change
    _create_data_link_fail(
        ss,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/1/1')),
            SampleNodeAddress(SampleAddress(id2, 1), 'mynode2'),
            dt(700),
            UserID('user')),
        TooManyDataLinksError(
            'More than 1 links from sample 12345678-90ab-cdef-1234-567890abcdee version 1'),
        update=True
    )


def test_get_data_link_fail_no_bad_args(samplestorage):
    _get_data_link_fail(samplestorage, None, None, ValueError(
        'exactly one of id_ or duid must be provided'))
    _get_data_link_fail(samplestorage, uuid.uuid4(), DataUnitID('1/1/1'), ValueError(
        'exactly one of id_ or duid must be provided'))


def test_get_data_link_fail_no_link(samplestorage):
    sid = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(sid, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    lid = uuid.UUID('1234567890abcdef1234567890abcde1')
    samplestorage.create_data_link(DataLink(
        lid,
        DataUnitID(UPA('1/1/1'), 'a'),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(100),
        UserID('user'))
    )

    _get_data_link_fail(
        samplestorage,
        uuid.UUID('1234567890abcdef1234567890abcde2'),
        None,
        NoSuchLinkError('12345678-90ab-cdef-1234-567890abcde2'))

    _get_data_link_fail(samplestorage, None, DataUnitID(UPA('1/2/1'), 'a'),
                        NoSuchLinkError('1/2/1:a'))
    _get_data_link_fail(samplestorage, None, DataUnitID(UPA('1/1/1'), 'b'),
                        NoSuchLinkError('1/1/1:b'))


def test_get_data_link_fail_expired_link(samplestorage):
    """
    Only fails for DUID based fetch
    """
    sid = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(sid, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    lid = uuid.UUID('1234567890abcdef1234567890abcde1')
    _create_and_expire_data_link(
        samplestorage,
        DataLink(
            lid,
            DataUnitID(UPA('1/1/1'), 'a'),
            SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
            dt(100),
            UserID('user')),
        dt(600),
        UserID('f')
    )

    _get_data_link_fail(samplestorage, None, DataUnitID(UPA('1/1/1'), 'a'),
                        NoSuchLinkError('1/1/1:a'))


def test_get_data_link_fail_too_many_links(samplestorage):
    sample_id = make_uuid()
    link_id = make_uuid()
    assert samplestorage.save_sample(
        SavedSample(sample_id, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    samplestorage.create_data_link(DataLink(
        link_id,
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(sample_id, 1), 'mynode'),
        dt(100),
        UserID('user'))
    )
    samplestorage.create_data_link(DataLink(
        link_id,
        DataUnitID(UPA('1/1/2')),
        SampleNodeAddress(SampleAddress(sample_id, 1), 'mynode'),
        dt(100),
        UserID('user'))
    )

    _get_data_link_fail(
        samplestorage, link_id, None, SampleStorageError(
            f'More than one data link found for ID {link_id}'))


def test_expire_and_get_data_link_via_duid(samplestorage):
    _expire_and_get_data_link_via_duid(samplestorage, 600, None, '')


def test_expire_and_get_data_link_via_duid_with_dataid(samplestorage):
    _expire_and_get_data_link_via_duid(
        samplestorage, -100, 'foo', 'acbd18db4cc2f85cedef654fccc4a4d8_')


def test_expire_and_get_data_link_via_id(samplestorage):
    _expire_and_get_data_link_via_id(samplestorage, 1000, None, '')


def test_expire_and_get_data_link_via_id_with_dataid(samplestorage):
    _expire_and_get_data_link_via_id(samplestorage, 10, 'foo', 'acbd18db4cc2f85cedef654fccc4a4d8_')


#
# Test failure conditions for expiration of data links.
#


def test_expire_data_link_fail_bad_args(samplestorage):
    ss = samplestorage
    e = dt(100)
    i = uuid.uuid4()
    d = DataUnitID('1/1/1')
    eb = datetime.datetime.fromtimestamp(400)
    u = UserID('u')

    _expire_data_link_fail(ss, None, u, i, None, ValueError(
        'expired cannot be a value that evaluates to false'))
    _expire_data_link_fail(ss, eb, u, None, d, ValueError('expired cannot be a naive datetime'))
    _expire_data_link_fail(ss, e, None, None, d, ValueError(
        'expired_by cannot be a value that evaluates to false'))
    _expire_data_link_fail(ss, e, u, i, d, ValueError(
        'exactly one of id_ or duid must be provided'))
    _expire_data_link_fail(ss, e, u, None, None, ValueError(
        'exactly one of id_ or duid must be provided'))


def test_expire_data_link_fail_no_id(samplestorage):
    sid = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(sid, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    lid = uuid.UUID('1234567890abcdef1234567890abcde1')
    samplestorage.create_data_link(DataLink(
        lid,
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(-100),
        UserID('user'))
    )

    _expire_data_link_fail(
        samplestorage, dt(1), UserID('u'), uuid.UUID('1234567890abcdef1234567890abcde2'), None,
        NoSuchLinkError('12345678-90ab-cdef-1234-567890abcde2'))


def test_expire_data_link_fail_with_id_expired(samplestorage):
    sid = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(sid, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    lid = uuid.UUID('1234567890abcdef1234567890abcde1')
    samplestorage.create_data_link(DataLink(
        lid,
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(-100),
        UserID('user'))
    )

    samplestorage.expire_data_link(dt(0), UserID('u'), lid)

    _expire_data_link_fail(
        samplestorage, dt(1), UserID('u'), lid, None,
        NoSuchLinkError('12345678-90ab-cdef-1234-567890abcde1'))


def test_expire_data_link_fail_with_id_too_many_links(samplestorage):
    sid = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(sid, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    lid = uuid.UUID('1234567890abcdef1234567890abcde1')
    samplestorage.create_data_link(DataLink(
        lid,
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(-100),
        UserID('usera'))
    )

    samplestorage.expire_data_link(dt(-50), UserID('u'), lid)

    samplestorage.create_data_link(DataLink(
        lid,
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(0),
        UserID('usera'))
    )

    _expire_data_link_fail(samplestorage, dt(1), UserID('u'), lid, None, SampleStorageError(
        'More than one data link found for ID 12345678-90ab-cdef-1234-567890abcde1'))


def test_expire_data_link_fail_no_duid(samplestorage):
    sid = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(sid, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    lid1 = uuid.UUID('1234567890abcdef1234567890abcde1')
    samplestorage.create_data_link(DataLink(
        lid1,
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(-100),
        UserID('usera'))
    )
    lid2 = uuid.UUID('1234567890abcdef1234567890abcde2')
    samplestorage.create_data_link(DataLink(
        lid2,
        DataUnitID(UPA('1/1/2'), 'foo'),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(-100),
        UserID('usera'))
    )

    _expire_data_link_fail(
        samplestorage, dt(1), UserID('u'), None, DataUnitID(UPA('1/2/1')),
        NoSuchLinkError('1/2/1'))

    _expire_data_link_fail(
        samplestorage, dt(1), UserID('u'), None, DataUnitID(UPA('1/1/2'), 'fo'),
        NoSuchLinkError('1/1/2:fo'))


def test_expire_data_link_fail_expire_before_create_by_id(samplestorage):
    sid = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(sid, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    lid1 = uuid.UUID('1234567890abcdef1234567890abcde1')
    samplestorage.create_data_link(DataLink(
        lid1,
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(100),
        UserID('someuser'))
    )

    _expire_data_link_fail(samplestorage, dt(99), UserID('u'), lid1, None, ValueError(
        'expired is < link created time: 100000'))


def test_expire_data_link_fail_race_condition(samplestorage):
    """
    Tests the case where a link is expire after pulling it from the DB in the first part of the
    method. See notes in the code.
    """

    sid = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(sid, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    lid1 = uuid.UUID('1234567890abcdef1234567890abcde1')
    samplestorage.create_data_link(DataLink(
        lid1,
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(sid, 1), 'mynode'),
        dt(-100),
        UserID('usera'))
    )

    # ok, we have the link doc from the db. This is what part 1 of the code does, and then
    # passes to part 2.
    linkdoc = samplestorage._col_data_link.get('1_1_1')

    # Now we simulate a race condition by expiring that link and calling part 2 of the expire
    # method. Part 2 should fail without modifying the links collection.
    samplestorage.expire_data_link(dt(200), UserID('foo'), lid1)

    with raises(Exception) as got:
        samplestorage._expire_data_link_pt2(linkdoc, dt(300), UserID('foo'), 'some id')
    assert_exception_correct(got.value, NoSuchLinkError('some id'))


def test_get_links_from_sample(samplestorage):
    sid1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    sid2 = uuid.UUID('1234567890abcdef1234567890abcdee')
    assert samplestorage.save_sample(SavedSample(
        sid1, UserID('user'),
        [SampleNode('mynode'), SampleNode('XmynodeX')], dt(1), 'foo')) is True
    assert samplestorage.save_sample_version(
        SavedSample(sid1, UserID('user'), [SampleNode('mynode1')], dt(2), 'foo')) == 2
    assert samplestorage.save_sample(
        SavedSample(sid2, UserID('user'), [SampleNode('mynode2')], dt(3), 'foo')) is True

    # shouldn't be found, different sample
    l1 = DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(sid2, 1), 'mynode2'),
        dt(-100),
        UserID('usera'))
    samplestorage.create_data_link(l1)

    # shouldn't be found, different version
    l2 = DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/2')),
        SampleNodeAddress(SampleAddress(sid1, 2), 'mynode1'),
        dt(-100),
        UserID('usera'))
    samplestorage.create_data_link(l2)

    # shouldn't be found, expired
    l3id = uuid.uuid4()
    _create_and_expire_data_link(
        samplestorage,
        DataLink(
            l3id,
            DataUnitID(UPA('1/1/3')),
            SampleNodeAddress(SampleAddress(sid1, 1), 'mynode'),
            dt(-100),
            UserID('usera')),
        dt(100),
        UserID('userb')
    )
    l3 = DataLink(
        l3id,
        DataUnitID(UPA('1/1/3')),
        SampleNodeAddress(SampleAddress(sid1, 1), 'mynode'),
        dt(-100),
        UserID('usera'),
        dt(100),
        UserID('userb'))

    # shouldn't be found, not created yet
    l4 = DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/4')),
        SampleNodeAddress(SampleAddress(sid1, 1), 'mynode'),
        dt(1000),
        UserID('usera'))
    samplestorage.create_data_link(l4)

    # shouldn't be found, not in ws list
    l5 = DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('10/1/1')),
        SampleNodeAddress(SampleAddress(sid1, 1), 'mynode'),
        dt(-100),
        UserID('usera'))
    samplestorage.create_data_link(l5)

    l6 = DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/5')),
        SampleNodeAddress(SampleAddress(sid1, 1), 'mynode'),
        dt(-100),
        UserID('usera'))
    samplestorage.create_data_link(l6)

    l7 = DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/2'), 'whee'),
        SampleNodeAddress(SampleAddress(sid1, 1), 'XmynodeX'),
        dt(-100),
        UserID('usera'))
    samplestorage.create_data_link(l7)

    l8id = uuid.uuid4()
    _create_and_expire_data_link(
        samplestorage,
        DataLink(
            l8id,
            DataUnitID(UPA('2/1/6'), ),
            SampleNodeAddress(SampleAddress(sid1, 1), 'mynode'),
            dt(-100),
            UserID('usera')),
        dt(800),
        UserID('usera')
    )
    l8 = DataLink(
        l8id,
        DataUnitID(UPA('2/1/6')),
        SampleNodeAddress(SampleAddress(sid1, 1), 'mynode'),
        dt(-100),
        UserID('usera'),
        dt(800),
        UserID('usera'))

    # test lower bound for expired
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid1, 1),
        [1, 2, 3],
        dt(100.001)
    )
    assert set(got) == {l6, l7, l8}  # order is undefined

    # test lower expired
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid1, 1),
        [1, 2, 3],
        dt(100)
    )
    assert set(got) == {l6, l7, l8, l3}  # order is undefined

    # test upper bound for expired
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid1, 1),
        [1, 2, 3],
        dt(800)
    )
    assert set(got) == {l6, l7, l8}  # order is undefined

    # test upper expired
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid1, 1),
        [1, 2, 3],
        dt(800.001)
    )
    assert set(got) == {l6, l7}  # order is undefined

    # test lower bound for created
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid1, 1),
        [1, 2, 3],
        dt(999.999)
    )
    assert set(got) == {l6, l7}  # order is undefined

    # test created
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid1, 1),
        [1, 2, 3],
        dt(1000)
    )
    assert set(got) == {l6, l7, l4}  # order is undefined

    # test limiting workspace ids
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid1, 1),
        [1],
        dt(500)
    )
    assert set(got) == {l6, l7}  # order is undefined

    # no results, no matching wsids
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid1, 1),
        [4, 5, 6],
        dt(500)
    )
    assert got == []

    # no results, no wsids
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid1, 1),
        [],
        dt(500)
    )
    assert got == []

    # test not filtering on WS id
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid1, 1),
        None,
        dt(500)
    )
    assert set(got) == {l5, l6, l7, l8}

    # no results, prior to created
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid1, 1),
        [1, 2, 3],
        dt(-100.001)
    )
    assert got == []

    # test different sample
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid2, 1),
        [1, 2, 3],
        dt(500)
    )
    assert got == [l1]

    # test different sample version
    got = samplestorage.get_links_from_sample(
        SampleAddress(sid1, 2),
        [1, 2, 3],
        dt(500)
    )
    assert got == [l2]


#
# Test failure conditions for getting links from samples
#


def test_get_links_from_sample_fail_bad_args(samplestorage):
    ss = samplestorage
    sa = SampleAddress(uuid.uuid4(), 1)
    ws = [1]
    ts = dt(1)
    tb = datetime.datetime.fromtimestamp(1)

    _get_links_from_sample_fail(ss, None, ws, ts, ValueError(
        'sample cannot be a value that evaluates to false'))
    _get_links_from_sample_fail(ss, sa, [1, None], ts, ValueError(
        'Index 1 of iterable readable_wsids cannot be a value that evaluates to false'))
    _get_links_from_sample_fail(ss, sa, ws, None, ValueError(
        'timestamp cannot be a value that evaluates to false'))
    _get_links_from_sample_fail(ss, sa, ws, tb, ValueError(
        'timestamp cannot be a naive datetime'))


def test_get_links_from_sample_fail_no_sample(samplestorage):
    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    id2 = uuid.UUID('1234567890abcdef1234567890abcdee')
    assert samplestorage.save_sample(
        SavedSample(id1, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    _get_links_from_sample_fail(
        samplestorage, SampleAddress(id2, 1), [1], dt(1), NoSuchSampleError(str(id2)))


def test_get_links_from_sample_fail_no_sample_version(samplestorage):
    id1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    assert samplestorage.save_sample(
        SavedSample(id1, UserID('user'), [SampleNode('mynode')], dt(1), 'foo')) is True

    _get_links_from_sample_fail(
        samplestorage, SampleAddress(id1, 2), [1], dt(1), NoSuchSampleVersionError(f'{id1} ver 2'))


def test_get_links_from_data(samplestorage):
    sid1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    sid2 = uuid.UUID('1234567890abcdef1234567890abcdee')
    assert samplestorage.save_sample(SavedSample(
        sid1, UserID('user'),
        [SampleNode('mynode'), SampleNode('XmynodeX')], dt(1), 'foo')) is True
    assert samplestorage.save_sample_version(
        SavedSample(sid1, UserID('user'), [SampleNode('mynode1')], dt(2), 'foo')) == 2
    assert samplestorage.save_sample(
        SavedSample(sid2, UserID('user'), [SampleNode('mynode2')], dt(3), 'foo')) is True

    # shouldn't be found, different ws
    l1 = DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('10/1/1')),
        SampleNodeAddress(SampleAddress(sid2, 1), 'mynode2'),
        dt(-100),
        UserID('usera'))
    samplestorage.create_data_link(l1)

    # shouldn't be found, different object
    l2 = DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/10/1')),
        SampleNodeAddress(SampleAddress(sid1, 2), 'mynode1'),
        dt(-100),
        UserID('usera'))
    samplestorage.create_data_link(l2)

    # shouldn't be found, different version
    l3 = DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/10')),
        SampleNodeAddress(SampleAddress(sid1, 2), 'mynode1'),
        dt(-100),
        UserID('usera'))
    samplestorage.create_data_link(l3)

    # shouldn't be found, expired
    l4id = uuid.uuid4()
    _create_and_expire_data_link(
        samplestorage,
        DataLink(
            l4id,
            DataUnitID(UPA('1/1/1'), 'expired'),
            SampleNodeAddress(SampleAddress(sid1, 1), 'mynode'),
            dt(-100),
            UserID('usera')),
        dt(100),
        UserID('userb')
    )
    l4 = DataLink(
        l4id,
        DataUnitID(UPA('1/1/1'), 'expired'),
        SampleNodeAddress(SampleAddress(sid1, 1), 'mynode'),
        dt(-100),
        UserID('usera'),
        dt(100),
        UserID('userb'))

    # shouldn't be found, not created yet
    l5 = DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1'), 'not created'),
        SampleNodeAddress(SampleAddress(sid1, 1), 'mynode'),
        dt(1000),
        UserID('usera'))
    samplestorage.create_data_link(l5)

    l6 = DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(sid1, 2), 'mynode1'),
        dt(-100),
        UserID('usera'))
    samplestorage.create_data_link(l6)

    l7 = DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1'), '1'),
        SampleNodeAddress(SampleAddress(sid1, 1), 'XmynodeX'),
        dt(-100),
        UserID('usera'))
    samplestorage.create_data_link(l7)

    l8id = uuid.uuid4()
    _create_and_expire_data_link(
        samplestorage,
        DataLink(
            l8id,
            DataUnitID(UPA('1/1/1'), '2'),
            SampleNodeAddress(SampleAddress(sid2, 1), 'mynode2'),
            dt(-100),
            UserID('usera')),
        dt(800),
        UserID('usera')
    )
    l8 = DataLink(
        l8id,
        DataUnitID(UPA('1/1/1'), '2'),
        SampleNodeAddress(SampleAddress(sid2, 1), 'mynode2'),
        dt(-100),
        UserID('usera'),
        dt(800),
        UserID('usera'))

    # test lower bound for expired
    got = samplestorage.get_links_from_data(UPA('1/1/1'), dt(100.001))
    assert set(got) == {l6, l7, l8}  # order is undefined

    # test lower expired
    got = samplestorage.get_links_from_data(UPA('1/1/1'), dt(100))
    assert set(got) == {l6, l7, l8, l4}  # order is undefined

    # test upper bound for expired
    got = samplestorage.get_links_from_data(UPA('1/1/1'), dt(800))
    assert set(got) == {l6, l7, l8}  # order is undefined

    # test upper expired
    got = samplestorage.get_links_from_data(UPA('1/1/1'), dt(800.001))
    assert set(got) == {l6, l7}  # order is undefined

    # test lower bound for created
    got = samplestorage.get_links_from_data(UPA('1/1/1'), dt(999.999))
    assert set(got) == {l6, l7}  # order is undefined

    # test created
    got = samplestorage.get_links_from_data(UPA('1/1/1'), dt(1000))
    assert set(got) == {l6, l7, l5}  # order is undefined

    # different wsid
    got = samplestorage.get_links_from_data(UPA('10/1/1'), dt(500))
    assert got == [l1]

    # different objid
    got = samplestorage.get_links_from_data(UPA('1/10/1'), dt(500))
    assert got == [l2]

    # different ver
    got = samplestorage.get_links_from_data(UPA('1/1/10'), dt(500))
    assert got == [l3]

    # no results, no matching objects
    got = samplestorage.get_links_from_data(UPA('9/1/1'), dt(500))
    assert got == []
    got = samplestorage.get_links_from_data(UPA('1/9/1'), dt(500))
    assert got == []
    got = samplestorage.get_links_from_data(UPA('1/1/9'), dt(500))
    assert got == []

    # no results, prior to created
    got = samplestorage.get_links_from_data(UPA('1/1/1'), dt(-100.001))
    assert got == []


def test_get_links_from_data_fail_bad_args(samplestorage):
    def _get_links_from_data_fail(samplestorage, upa, ts, expected):
        with raises(Exception) as got:
            samplestorage.get_links_from_data(upa, ts)
        assert_exception_correct(got.value, expected)

    ss = samplestorage
    u = UPA('1/1/1')
    ts = dt(1)
    td = datetime.datetime.fromtimestamp(1)

    _get_links_from_data_fail(ss, None, ts, ValueError(
        'upa cannot be a value that evaluates to false'))
    _get_links_from_data_fail(ss, u, None, ValueError(
        'timestamp cannot be a value that evaluates to false'))
    _get_links_from_data_fail(ss, u, td, ValueError(
        'timestamp cannot be a naive datetime'))


def test_has_data_link(samplestorage):
    sid1 = uuid.UUID('1234567890abcdef1234567890abcdef')
    sid2 = uuid.UUID('1234567890abcdef1234567890abcdee')
    sid3 = uuid.UUID('1234567890abcdef1234567890abcded')
    assert samplestorage.save_sample(SavedSample(
        sid1, UserID('user'),
        [SampleNode('mynode'), SampleNode('XmynodeX')], dt(1), 'foo')) is True
    assert samplestorage.save_sample_version(
        SavedSample(sid1, UserID('user'), [SampleNode('mynode1')], dt(2), 'foo')) == 2
    assert samplestorage.save_sample(
        SavedSample(sid2, UserID('user'), [SampleNode('mynode2')], dt(3), 'foo')) is True
    assert samplestorage.save_sample(
        SavedSample(sid3, UserID('user'), [SampleNode('mynode4')], dt(3), 'foo')) is True

    samplestorage.create_data_link(DataLink(
        uuid.uuid4(),
        DataUnitID(UPA('1/1/1')),
        SampleNodeAddress(SampleAddress(sid2, 1), 'mynode2'),
        dt(-100),
        UserID('usera')))

    _create_and_expire_data_link(
        samplestorage,
        DataLink(
            uuid.uuid4(),
            DataUnitID(UPA('1/2/1'), '2'),
            SampleNodeAddress(SampleAddress(sid1, 2), 'mynode1'),
            dt(-100),
            UserID('usera')),
        dt(800),
        UserID('usera'))

    assert samplestorage.has_data_link(UPA('1/1/1'), sid2) is True
    # sample version & expired state shouldn't matter
    assert samplestorage.has_data_link(UPA('1/2/1'), sid1) is True
    # wrong sample
    assert samplestorage.has_data_link(UPA('1/2/1'), sid3) is False
    # wrong object id
    assert samplestorage.has_data_link(UPA('1/2/1'), sid2) is False
    # wrong version
    assert samplestorage.has_data_link(UPA('1/2/2'), sid1) is False
    # wrong wsid
    assert samplestorage.has_data_link(UPA('2/2/1'), sid1) is False


def test_has_data_link_fail_bad_args(samplestorage):
    def _has_data_link_fail(upa, sample, expected):
        with raises(Exception) as got:
            samplestorage.has_data_link(upa, sample)
        assert_exception_correct(got.value, expected)

    u = UPA('1/1/1')
    s = uuid.UUID('1234567890abcdef1234567890abcdef')

    _has_data_link_fail(None, s, ValueError(
        'upa cannot be a value that evaluates to false'))
    _has_data_link_fail(u, None, ValueError(
        'sample cannot be a value that evaluates to false'))
