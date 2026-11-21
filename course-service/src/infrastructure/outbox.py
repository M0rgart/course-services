import asyncio
import logging
from contextlib import suppress

from sqlalchemy.exc import SQLAlchemyError

from src.application.ports import EventPublisher, OutboxMessage, UnitOfWorkFactory

logger = logging.getLogger(__name__)


class OutboxPublishError(Exception):
    pass


class LoggingEventPublisher:
    async def publish(self, message: OutboxMessage) -> None:
        logger.info("Published event type=%s id=%s", message.event_type, message.id)


class OutboxDispatcher:
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        publisher: EventPublisher,
        polling_interval: float = 0.25,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._publisher = publisher
        self._polling_interval = polling_interval

    async def dispatch_once(self) -> bool:
        async with self._unit_of_work_factory.create() as unit_of_work:
            message = await unit_of_work.outbox.claim_next()
        if message is None:
            return False
        try:
            await self._publisher.publish(message)
        except OutboxPublishError as exc:
            logger.error("Outbox delivery failed for event %s: %s", message.id, exc)
            async with self._unit_of_work_factory.create() as unit_of_work:
                await unit_of_work.outbox.mark_failed(message.id, str(exc))
            return True
        async with self._unit_of_work_factory.create() as unit_of_work:
            await unit_of_work.outbox.mark_completed(message.id)
        return True

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                processed = await self.dispatch_once()
            except SQLAlchemyError:
                logger.exception("Outbox polling failed")
                processed = False
            if not processed:
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), self._polling_interval)
