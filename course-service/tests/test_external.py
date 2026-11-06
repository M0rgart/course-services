import asyncio
import threading
import time
from uuid import uuid4

import pytest
from src.core.config import ExternalServiceSettings
from src.core.external import (
    AsyncExternalService,
    ExternalServiceError,
    ExternalServiceTimeoutError,
    _post_json,
)


@pytest.mark.asyncio
async def test_external_calls_respect_concurrency_limit(monkeypatch) -> None:
    active = 0
    maximum_active = 0
    counter_lock = threading.Lock()

    def fake_post_json(url: str, payload: dict, timeout: float) -> dict:
        nonlocal active, maximum_active
        with counter_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.02)
        with counter_lock:
            active -= 1
        return {"auto_score": payload["mark"]}

    monkeypatch.setattr("src.core.external._post_json", fake_post_json)
    service = AsyncExternalService(
        ExternalServiceSettings(
            url="https://grader.example.test/review",
            timeout_seconds=1,
            max_concurrency=2,
        )
    )

    await asyncio.gather(
        *(
            service.evaluate_submission(uuid4(), uuid4(), float(index))
            for index in range(8)
        )
    )

    assert maximum_active == 2


@pytest.mark.asyncio
async def test_external_call_times_out() -> None:
    service = AsyncExternalService(
        ExternalServiceSettings(
            timeout_seconds=0.01,
            simulation_delay_seconds=0.05,
            max_concurrency=1,
        )
    )

    with pytest.raises(ExternalServiceTimeoutError):
        await service.evaluate_submission(uuid4(), uuid4(), 75.0)


def test_external_http_request_contract(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self) -> bytes:
            return b'{"auto_score": 82}'

    def fake_urlopen(request, timeout: float):
        assert request.full_url == "https://grader.example.test/review"
        assert request.method == "POST"
        assert request.get_header("Content-type") == "application/json"
        assert timeout == 1.5
        return FakeResponse()

    monkeypatch.setattr("src.core.external.urlopen", fake_urlopen)
    assert _post_json(
        "https://grader.example.test/review", {"submission_id": "abc"}, 1.5
    ) == {"auto_score": 82}

    with pytest.raises(ExternalServiceError):
        _post_json("file:///tmp/grader", {}, 1.5)
