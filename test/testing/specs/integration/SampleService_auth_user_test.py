# ###########################
# Auth user lookup tests
# ###########################

# These tests cover the integration of the entire system and do not go into details - that's
# what unit tests are for. As such, typically each method will get a single happy path test and
# a single unhappy path test unless otherwise warranted.

from pytest import raises
from SampleService.core.acls import AdminPermission
from SampleService.core.user import UserID
from SampleService.core.user_lookup import InvalidTokenError, KBaseUserLookup

# Utilities
from testing.shared.test_constants import (
    TOKEN1,
    TOKEN2,
    TOKEN3,
    TOKEN4,
    TOKEN_SERVICE,
    USER1,
    USER2,
    USER3,
    USER4,
)
from testing.shared.test_utils import assert_exception_correct


def _user_lookup_fail(userlookup, users, expected):
    with raises(Exception) as got:
        userlookup.invalid_users(users)
    assert_exception_correct(got.value, expected)


def _user_lookup_build_fail(url, token, expected):
    with raises(Exception) as got:
        KBaseUserLookup(url, token)
    assert_exception_correct(got.value, expected)


def _is_admin_fail(userlookup, user, expected):
    with raises(Exception) as got:
        userlookup.is_admin(user)
    assert_exception_correct(got.value, expected)


# Tests


# TODO: Not sure we should be testing token corruption.
# Shouldn't that be covered by auth service tests? I suppose it is
# sensible to simulate all _specific_ auth service errors caught by
# this service.
def test_user_lookup_build_fail_bad_token(auth_url):
    _user_lookup_build_fail(
        auth_url,
        "tokentokentoken!",
        InvalidTokenError("KBase auth server reported token is invalid."),
    )


# TODO: not valid tests?
# The "404" behavior of the server is really out of scope for its api -
# an errant url can invoke any service or non-service.
#
def test_user_lookup_build_fail_bad_auth_url(auth_url):
    _user_lookup_build_fail(
        auth_url + "/foo",
        TOKEN1,
        IOError("Error from KBase auth server: HTTP 404 Not Found"),
    )


def test_user_lookup(auth_url):
    ul = KBaseUserLookup(auth_url, TOKEN1)
    assert ul.invalid_users([]) == []
    assert ul.invalid_users([UserID(USER1), UserID(USER2), UserID(USER3)]) == []


def test_user_lookup_cache(auth_url):
    ul = KBaseUserLookup(auth_url, TOKEN1)
    assert ul._valid_cache.get(USER1, default=False) is False
    assert ul._valid_cache.get(USER2, default=False) is False
    ul.invalid_users([UserID(USER1)])
    assert ul._valid_cache.get(USER1, default=False) is True
    assert ul._valid_cache.get(USER2, default=False) is False


def test_user_lookup_bad_users(auth_url):
    ul = KBaseUserLookup(auth_url, TOKEN1)
    assert (
        ul.invalid_users(
            [
                UserID("nouserhere"),
                UserID(USER1),
                UserID(USER2),
                UserID("whooptydoo"),
                UserID(USER3),
            ]
        )
        == [UserID("nouserhere"), UserID("whooptydoo")]
    )


def test_user_lookup_fail_bad_args(auth_url):
    ul = KBaseUserLookup(auth_url, TOKEN1)
    _user_lookup_fail(ul, None, ValueError("usernames cannot be None"))
    _user_lookup_fail(
        ul,
        [UserID("foo"), UserID("bar"), None],
        ValueError(
            "Index 2 of iterable usernames cannot be a value that evaluates to false"
        ),
    )


def test_user_lookup_fail_bad_username(auth_url):
    userlookup = KBaseUserLookup(auth_url, TOKEN1)
    with raises(Exception) as exception:
        userlookup.is_admin([UserID("1")])
        # Only use the prefix for the error message, as the rest of it, supplied by the
        # auth service, is quite long, and the precise text is not important here.
        expected = (
            "The KBase auth server is being very assertive about one of the usernames "
            "being illegal"
        )
        assert exception.value.startswith(expected)


def test_is_admin(auth_url):
    n = AdminPermission.NONE
    r = AdminPermission.READ
    f = AdminPermission.FULL

    def check_is_admin(results, full_roles=None, read_roles=None):
        ul = KBaseUserLookup(auth_url, TOKEN_SERVICE, full_roles, read_roles)

        for token, username, roles in zip(
            [TOKEN1, TOKEN2, TOKEN3, TOKEN4], [USER1, USER2, USER3, USER4], results
        ):
            assert ul.is_admin(token) == (roles, username)

    check_is_admin([n, n, n, n])
    check_is_admin([f, f, n, n], ["fulladmin1"])
    check_is_admin([n, f, n, n], ["fulladmin2"])
    check_is_admin([n, n, r, n], None, ["readadmin1"])
    check_is_admin([n, r, n, n], None, ["readadmin2"])
    check_is_admin([n, f, n, n], ["fulladmin2"], ["readadmin2"])
    check_is_admin([n, f, r, n], ["fulladmin2"], ["readadmin1"])


def test_is_admin_cache(auth_url):
    ul = KBaseUserLookup(auth_url, TOKEN_SERVICE)
    assert ul._admin_cache.get(TOKEN1, default=False) is False
    assert ul._admin_cache.get(TOKEN2, default=False) is False
    ul.is_admin(TOKEN1)
    assert ul._admin_cache.get(TOKEN1, default=False) is not False
    assert ul._admin_cache.get(TOKEN2, default=False) is False


def test_is_admin_fail_bad_input(auth_url):
    ul = KBaseUserLookup(auth_url, TOKEN_SERVICE)

    _is_admin_fail(
        ul, None, ValueError("token cannot be a value that evaluates to false")
    )
    _is_admin_fail(
        ul, "", ValueError("token cannot be a value that evaluates to false")
    )


def test_is_admin_fail_bad_token(auth_url):
    ul = KBaseUserLookup(auth_url, TOKEN_SERVICE)

    _is_admin_fail(
        ul,
        "bad token here",
        InvalidTokenError("KBase auth server reported token is invalid."),
    )
