"""Offline HTTP contract tests: no live Greenhouse requests or database writes."""

import httpx
import pytest

from app.ingestion.greenhouse import fetch_jobs, validated_token


def synthetic_posting():
    return {
        "id": 501,
        "title": "Synthetic Test Engineer",
        "absolute_url": "https://example.org/jobs/501",
        "location": {"name": "Test City"},
    }


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410, 422])
def test_permanent_http_failures_are_not_retried(status):
    requested = []

    def handler(request):
        requested.append(request)
        return httpx.Response(status)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            fetch_jobs("syntheticboard", client=client, sleep=lambda _: None)
    assert len(requested) == 1


def test_redirect_is_not_followed_or_used_to_fetch_an_untrusted_host():
    requested = []

    def handler(request):
        requested.append(request)
        return httpx.Response(302, headers={"Location": "https://private.example/redirect"})

    with httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            fetch_jobs("syntheticboard", client=client, sleep=lambda _: None)
    assert len(requested) == 1
    assert requested[0].url.host == "boards-api.greenhouse.io"


def test_rate_limit_wait_is_bounded_then_successful():
    calls = []
    delays = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "999"})
        return httpx.Response(200, json={"jobs": [synthetic_posting()], "meta": {"total": 1}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        jobs = fetch_jobs("syntheticboard", client=client, sleep=delays.append)
    assert len(jobs) == 1
    assert len(calls) == 2
    assert delays == [30.0]


def test_transport_exception_retries_only_up_to_configured_bound():
    calls = []
    delays = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectError("synthetic network outage", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.ConnectError, match="synthetic network outage"):
            fetch_jobs("syntheticboard", client=client, sleep=delays.append)
    assert len(calls) == 3
    assert delays == [1, 2]


@pytest.mark.parametrize("payload", [
    {"jobs": None},
    {"jobs": {}},
    {"jobs": [None]},
    {"jobs": [synthetic_posting(), "not-an-object"]},
    {"jobs": [synthetic_posting()], "meta": {"total": 2}},
    [],
])
def test_malformed_or_incomplete_feed_never_reports_success(payload):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )
    ) as client:
        with pytest.raises(ValueError):
            fetch_jobs("syntheticboard", client=client, sleep=lambda _: None)


def test_unparseable_json_is_rejected():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="not valid JSON")
        )
    ) as client:
        with pytest.raises(ValueError):
            fetch_jobs("syntheticboard", client=client)


@pytest.mark.parametrize("unsafe_board", [
    "https://boards-api.greenhouse.io/v1/boards/foo",
    "board%2Fsubpath",
    "a/b",
    "../secrets",
    "board?content=true",
    "a" * 121,
])
def test_board_tokens_cannot_override_host_or_request_path(unsafe_board):
    with pytest.raises(ValueError):
        validated_token(unsafe_board)


def test_valid_board_normalizes_case_without_extra_query_fields():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"jobs": [], "meta": {"total": 0}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert fetch_jobs("SYNTHETICBOARD", client=client) == []
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/v1/boards/syntheticboard/jobs"
    assert requests[0].url.query == b""
