import time
import uuid

from pytest import raises
from SampleService.core.sample import SampleNode, SavedSample, SubSampleType
from SampleService.core.user import UserID
from testing.shared.common import dt
from testing.shared.test_utils import assert_exception_correct

TEST_NODE = SampleNode("foo")


#
# Testing
#


def test_start_consistency_checker_fail_bad_args(samplestorage):
    with raises(Exception) as got:
        samplestorage.start_consistency_checker(interval_sec=0)
    assert_exception_correct(got.value, ValueError("interval_sec must be > 0"))


def test_consistency_checker_run(samplestorage):
    # here we just test that stopping and starting the checker will clean up the db.
    # The cleaning functionality is tested thoroughly above.
    # The db could be in an unclean state if a sample server does down mid save and doesn't
    # come back up.
    n1 = SampleNode("root")
    n2 = SampleNode("kid1", SubSampleType.TECHNICAL_REPLICATE, "root")
    n3 = SampleNode("kid2", SubSampleType.SUB_SAMPLE, "kid1")
    n4 = SampleNode("kid3", SubSampleType.TECHNICAL_REPLICATE, "root")

    id_ = uuid.UUID("1234567890abcdef1234567890abcdef")

    assert (
        samplestorage.save_sample(
            SavedSample(id_, UserID("u"), [n1, n2, n3, n4], dt(1), "foo")
        )
        is True
    )

    assert (
        samplestorage.save_sample_version(
            SavedSample(id_, UserID("u"), [n1, n2, n3, n4], dt(1), "bar")
        )
        == 2
    )

    # this is very naughty
    sample = samplestorage._col_sample.find({}).next()
    uuidver2 = sample["vers"][1]

    samplestorage._col_nodes.update_match(
        {"uuidver": uuidver2, "name": "kid2"}, {"ver": -1}
    )

    samplestorage.start_consistency_checker(interval_sec=1)
    samplestorage.start_consistency_checker(
        interval_sec=1
    )  # test that running twice does nothing

    time.sleep(0.5)

    assert (
        samplestorage._col_nodes.find({"uuidver": uuidver2, "name": "kid2"}).next()[
            "ver"
        ]
        == -1
    )

    time.sleep(1)

    assert samplestorage._col_version.count() == 2
    assert samplestorage._col_ver_edge.count() == 2
    assert samplestorage._col_nodes.count() == 8
    assert samplestorage._col_node_edge.count() == 8

    for v in samplestorage._col_version.all():
        assert v["ver"] == 2 if v["uuidver"] == uuidver2 else 1

    for v in samplestorage._col_nodes.all():
        assert v["ver"] == 2 if v["uuidver"] == uuidver2 else 1

    # test that pausing stops updating
    samplestorage.stop_consistency_checker()
    samplestorage.stop_consistency_checker()  # test that running twice in a row does nothing

    samplestorage._col_nodes.update_match(
        {"uuidver": uuidver2, "name": "kid2"}, {"ver": -1}
    )

    time.sleep(1.5)
    assert (
        samplestorage._col_nodes.find({"uuidver": uuidver2, "name": "kid2"}).next()[
            "ver"
        ]
        == -1
    )

    samplestorage.start_consistency_checker(1)

    time.sleep(1.5)

    assert (
        samplestorage._col_nodes.find({"uuidver": uuidver2, "name": "kid2"}).next()[
            "ver"
        ]
        == 2
    )

    # leaving the checker running can occasionally interfere with other tests, deleting documents
    # that are in the middle of the save process. Stop the checker and wait until the job must've
    # run.
    samplestorage.stop_consistency_checker()
    time.sleep(1)
