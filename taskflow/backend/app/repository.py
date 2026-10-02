"""Task persistence."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Task


def list_tasks(db: Session) -> list[Task]:
    statement = select(Task).order_by(Task.created_at.desc(), Task.id.desc())
    return list(db.scalars(statement).all())


def get_task(db: Session, task_id: int) -> Task | None:
    return db.get(Task, task_id)


def create_task(db: Session, title: str, description: str) -> Task:
    task = Task(
        title=title,
        description=description,
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def apply_update(db: Session, task: Task, changes: dict) -> Task:
    for key, value in changes.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task: Task) -> None:
    db.delete(task)
    db.commit()
