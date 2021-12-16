# ###########################
# Auth user lookup tests
# ###########################


from pytest import raises
from SampleService.core.user_lookup import KBaseUserLookup
# Utilities
from testing.shared.test_constants import TOKEN1
from testing.shared.test_utils import assert_exception_correct


def _user_lookup_build_fail(url, token, expected):
    with raises(Exception) as got:
        KBaseUserLookup(url, token)
    assert_exception_correct(got.value, expected)


def _is_admin_fail(userlookup, user, expected):
    with raises(Exception) as got:
        userlookup.is_admin(user)
    assert_exception_correct(got.value, expected)


# Tests

def test_user_lookup_build_fail_bad_args():
    _user_lookup_build_fail(
        '', 'foo', ValueError('auth_url cannot be a value that evaluates to false'))
    _user_lookup_build_fail(
        'http://foo.com', '', ValueError('auth_token cannot be a value that evaluates to false'))


# TODO: we should provide such an endpoint in the mock service so
# devs don't feel the need to involve third-party web services
def test_user_lookup_build_fail_not_auth_url():
    _user_lookup_build_fail(
        'https://httpbin.org/status/404',
        TOKEN1,
        IOError('Non-JSON response from KBase auth server, status code: 404'))
