"""Task CRUD."""

from collections.abc import Callable, Iterator
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import ensure_schema
from app.logging_config import get_logger, redact
from app.models import Task
from app.repository import apply_update, create_task, delete_task, get_task, list_tasks
from app.schemas import TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = get_logger()
T = TypeVar("T")


def get_db(request: Request) -> Iterator[Session]:
    if not request.app.state.schema_ready:
        try:
            ensure_schema(request.app.state.engine)
            request.app.state.schema_ready = True
        except Exception as exc:  # noqa: BLE001
            _log_db_error(request, exc)
            raise HTTPException(status_code=503, detail="Database unavailable") from exc
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def _log_db_error(request: Request, exc: Exception) -> None:
    secret = request.app.state.settings.database_password
    logger.error(
        "database error",
        extra={
            "endpoint": f"{request.method} {request.url.path}",
            "status_code": 503,
            "error": redact(str(exc), secret),
        },
    )


def _run(request: Request, db: Session, action: Callable[[], T]) -> T:
    try:
        return action()
    except SQLAlchemyError as exc:
        db.rollback()
        _log_db_error(request, exc)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@router.get("", response_model=list[TaskRead])
def read_tasks(request: Request, db: Session = Depends(get_db)) -> list[Task]:
    return _run(request, db, lambda: list_tasks(db))


@router.post("", response_model=TaskRead, status_code=201)
def add_task(payload: TaskCreate, request: Request, db: Session = Depends(get_db)) -> Task:
    return _run(
        request,
        db,
        lambda: create_task(db, payload.title, payload.description),
    )


@router.put("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> Task:
    def action() -> Task:
        task = get_task(db, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        return apply_update(db, task, changes)

    return _run(request, db, action)


@router.delete("/{task_id}", status_code=204)
def remove_task(task_id: int, request: Request, db: Session = Depends(get_db)) -> Response:
    def action() -> None:
        task = get_task(db, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        delete_task(db, task)

    _run(request, db, action)
    return Response(status_code=204)
