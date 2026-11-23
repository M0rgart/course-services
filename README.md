# course-services

Монорепозиторий backend-сервисов для курсов.

## Сервисы

- **bff** — Backend-for-Frontend
- **code-coordinator** — координатор кода
- **course-service** — основной сервис курсов (FastAPI)
- **plagiarism-service** — проверка на плагиат

## Запуск course-service

```bash
cd course-service
uv sync --all-groups
uv run uvicorn src.main:app --host 127.0.0.1 --port 8888 --env-file .env --log-config log-config.yaml
```

Открыть: http://127.0.0.1:8888/docs

## Тесты

```bash
cd course-service
uv run pytest
```

## Линтеры

```bash
uv run ruff check ./src ./tests ./migrations
uv run black --check ./src ./tests ./migrations ./generated
uv run isort ./src ./tests ./migrations ./generated --check
uv run mypy ./src ./tests --config-file pyproject.toml
uv run pylint ./src --rcfile pyproject.toml
```
