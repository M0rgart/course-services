class DomainError(Exception):
    code: str = "DOMAIN_ERROR"
    status: int = 400
    message: str = "Domain error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    status = 404
    message = "Ресурс не найден"


class CourseNotFoundError(NotFoundError):
    code = "COURSE_NOT_FOUND"
    message = "Курс не существует"


class AssignmentNotFoundError(NotFoundError):
    code = "ASSIGNMENT_NOT_FOUND"
    message = "Задание не существует"


class SubmissionNotFoundError(NotFoundError):
    code = "SUBMISSION_NOT_FOUND"
    message = "Сдача не существует"


class ReviewNotFoundError(NotFoundError):
    code = "REVIEW_NOT_FOUND"
    message = "Проверка не существует"


class ForbiddenError(DomainError):
    code = "FORBIDDEN"
    status = 403
    message = "Недостаточно прав"


class ConflictError(DomainError):
    code = "CONFLICT"
    status = 409
    message = "Конфликт состояния"


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"
    status = 422
    message = "Ошибка валидации"


class IdempotencyConflictError(ConflictError):
    code = "IDEMPOTENCY_CONFLICT"
    message = "Повторный запрос с тем же Idempotency-Key и другими данными"


class RateLimitError(DomainError):
    code = "RATE_LIMITED"
    status = 429
    message = "Слишком много запросов"