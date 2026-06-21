import pytest
from anthropic import APIStatusError, BadRequestError

from messygit import llm
from messygit.config import ANTHROPIC_INSUFFICIENT_BALANCE_MESSAGE


class FakeBadRequest(BadRequestError):
    """A BadRequestError we can build without a live httpx response.

    The real SDK error needs an httpx.Response; the balance helpers only read
    .status_code/.body/.message/.request_id and check isinstance(BadRequestError),
    so we override __init__ and set just those attributes.
    """

    def __init__(self, *, body=None, message="", status_code=400, request_id=None):
        self.body = body
        self.message = message
        self.status_code = status_code
        self.request_id = request_id


class FakeAPIStatusError(APIStatusError):
    """A non-BadRequest APIStatusError (e.g. a 402 or 5xx)."""

    def __init__(self, *, body=None, message="", status_code=500, request_id=None):
        self.body = body
        self.message = message
        self.status_code = status_code
        self.request_id = request_id


def billing_body(message="Your credit balance is too low"):
    return {"type": "error", "error": {"type": "billing_error", "message": message}}


# --- _is_insufficient_balance_or_billing ----------------------------------

def test_status_402_is_billing_even_without_billing_type():
    exc = FakeAPIStatusError(status_code=402, body={"error": {"type": "invalid_request_error"}})
    assert llm._is_insufficient_balance_or_billing(exc) is True


def test_nested_billing_error_type_is_detected():
    exc = FakeAPIStatusError(status_code=400, body=billing_body())
    assert llm._is_insufficient_balance_or_billing(exc) is True


@pytest.mark.parametrize("hint", [
    "Your credit balance is too low to access the API.",
    "balance too low",
    "insufficient credit on this account",
    "the account has no credit",
    "you are out of credit",
])
def test_bad_request_balance_hints_in_message(hint):
    exc = FakeBadRequest(status_code=400, message=hint)
    assert llm._is_insufficient_balance_or_billing(exc) is True


def test_bad_request_hint_in_nested_body_message():
    exc = FakeBadRequest(
        status_code=400,
        message="Bad request",
        body={"error": {"type": "invalid_request_error", "message": "credit balance is too low"}},
    )
    assert llm._is_insufficient_balance_or_billing(exc) is True


def test_unrelated_bad_request_is_not_billing():
    exc = FakeBadRequest(status_code=400, message="max_tokens: must be greater than 0")
    assert llm._is_insufficient_balance_or_billing(exc) is False


def test_generic_non_billing_status_error_is_not_billing():
    # A 500 with no billing markers: must not be misclassified as a balance issue.
    exc = FakeAPIStatusError(status_code=500, message="internal server error")
    assert llm._is_insufficient_balance_or_billing(exc) is False


def test_hint_matching_is_case_insensitive():
    exc = FakeBadRequest(status_code=400, message="CREDIT BALANCE TOO LOW")
    assert llm._is_insufficient_balance_or_billing(exc) is True


# --- _insufficient_balance_user_message -----------------------------------

def test_user_message_without_request_id_is_the_base_message():
    exc = FakeBadRequest(status_code=400, message="balance too low", request_id=None)
    assert llm._insufficient_balance_user_message(exc) == ANTHROPIC_INSUFFICIENT_BALANCE_MESSAGE


def test_user_message_appends_request_id_when_present():
    exc = FakeBadRequest(status_code=400, message="balance too low", request_id="req_abc123")
    msg = llm._insufficient_balance_user_message(exc)
    assert msg.startswith(ANTHROPIC_INSUFFICIENT_BALANCE_MESSAGE)
    assert msg.endswith("Request ID for support: req_abc123.")


# --- nested-body helpers (defensive parsing) ------------------------------

@pytest.mark.parametrize("body", [None, "a string", 42, {"error": "not a dict"}, {}])
def test_nested_helpers_tolerate_malformed_bodies(body):
    assert llm._nested_api_error_type(body) is None
    assert llm._nested_api_error_message(body) == ""
