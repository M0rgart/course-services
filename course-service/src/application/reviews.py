from uuid import UUID

from src.application.common import (
    _check_idempotency,
    _get_submission,
    _remember_idempotency,
    _require_submission_access,
)
from src.application.ports import Repository
from src.core import models
from src.core.exceptions import (
    ConflictError,
    ForbiddenError,
    ReviewNotFoundError,
)
from src.core.external import AsyncExternalService, ExternalServiceError
from src.web.schemas import (
    Review,
    ReviewCreate,
    ReviewUpdate,
)


async def create_review(
    repository: Repository,
    key: str,
    submission_id: UUID,
    payload: ReviewCreate,
    actor_id: UUID,
    role: str,
    external_service: AsyncExternalService,
) -> Review:
    submission, course = await _get_submission(repository, submission_id)
    if role != "admin" and course.teacher_id != actor_id:
        raise ForbiddenError()
    payload_json = payload.model_dump_json()
    cached = await _check_idempotency(
        repository, key, payload_json, f"create_review:{submission_id}", actor_id
    )
    if cached is not None:
        return Review.model_validate(cached)
    if submission.review_id is not None:
        raise ConflictError("Сдача уже проверена")
    mark = payload.mark
    auto_score = payload.auto_score
    feedback = payload.feedback
    if payload.type.value == "AUTO":
        external_result = await external_service.evaluate_submission(
            submission_id, submission.assignment_id, payload.mark
        )
        score = external_result.get("auto_score")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
            raise ExternalServiceError("Внешний сервис вернул некорректную оценку")
        auto_score = float(score)
        mark = auto_score
        if isinstance(external_result.get("feedback"), str):
            feedback = external_result["feedback"]
    review = models.Review(
        submission_id=submission_id,
        reviewer_id=actor_id,
        type=models.ReviewType(payload.type),
        feedback=feedback,
        mark=mark,
        auto_score=auto_score,
        manual=payload.manual,
        status=models.ReviewStatus.COMPLETED,
    )
    repository.add(review)
    await repository.flush()
    submission.review_id = review.id
    submission.status = models.SubmissionStatus.COMPLETED
    await repository.flush()
    response = Review.model_validate(review)
    await _remember_idempotency(
        repository,
        key,
        payload_json,
        response.model_dump(),
        f"create_review:{submission_id}",
        actor_id,
    )
    return response


async def get_review(
    repository: Repository, submission_id: UUID, actor_id: UUID, role: str
) -> Review:
    submission, course = await _get_submission(repository, submission_id)
    if submission.review_id is None:
        raise ReviewNotFoundError()
    await _require_submission_access(submission, course, actor_id, role)
    review = await repository.get(models.Review, submission.review_id)
    if review is None:
        raise ReviewNotFoundError()
    return Review.model_validate(review)


async def update_review(
    repository: Repository,
    submission_id: UUID,
    payload: ReviewUpdate,
    actor_id: UUID,
    role: str,
) -> Review:
    submission, course = await _get_submission(repository, submission_id)
    if submission.review_id is None:
        raise ReviewNotFoundError()
    if role != "admin" and course.teacher_id != actor_id:
        raise ForbiddenError()
    review = await repository.get(models.Review, submission.review_id)
    if review is None:
        raise ReviewNotFoundError()
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(review, field, value)
    await repository.flush()
    return Review.model_validate(review)
