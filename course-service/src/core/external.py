import asyncio
import json
from collections.abc import Mapping
from typing import Any
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

from src.core.config import ExternalServiceSettings
from src.core.exceptions import DomainError


class ExternalServiceError(DomainError):
    code = "EXTERNAL_SERVICE_ERROR"
    status = 502
    message = "Ошибка внешнего сервиса"


class ExternalServiceTimeoutError(ExternalServiceError):
    code = "EXTERNAL_SERVICE_TIMEOUT"
    status = 504
    message = "Внешний сервис не ответил вовремя"


def _post_json(url: str, payload: Mapping[str, Any], timeout: float) -> dict[str, Any]:
    parsed_url = urlsplit(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ExternalServiceError("URL внешнего сервиса должен использовать HTTP или HTTPS")
    request = Request(  # noqa: S310 - the URL scheme is validated immediately above
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        result = json.loads(response.read())
    if not isinstance(result, dict):
        raise ExternalServiceError("Внешний сервис вернул некорректный ответ")
    return result


class AsyncExternalService:
    """Асинхронный адаптер к проверяющему сервису с лимитом запросов."""

    def __init__(self, settings: ExternalServiceSettings) -> None:
        self.url = settings.url
        self.timeout_seconds = settings.timeout_seconds
        self.simulation_delay_seconds = settings.simulation_delay_seconds
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def evaluate_submission(
        self, submission_id: UUID, assignment_id: UUID, mark: float
    ) -> dict[str, Any]:
        payload = {
            "submission_id": str(submission_id),
            "assignment_id": str(assignment_id),
            "mark": mark,
        }
        try:
            async with self._semaphore:
                async with asyncio.timeout(self.timeout_seconds):
                    if self.url is None:
                        await asyncio.sleep(self.simulation_delay_seconds)
                        return {"auto_score": mark}
                    return await asyncio.to_thread(
                        _post_json, self.url, payload, self.timeout_seconds
                    )
        except TimeoutError as exc:
            raise ExternalServiceTimeoutError() from exc
        except (URLError, OSError, json.JSONDecodeError) as exc:
            raise ExternalServiceError() from exc
