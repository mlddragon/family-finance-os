from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from dillon_finances.actors import ActorContext, actor_context_to_json, derive_actor_context
from dillon_finances.models import Job


def record_job(
    session: Session,
    *,
    job_type: str,
    status: str,
    actor: str,
    actor_context: Optional[ActorContext] = None,
    input_json: Optional[str] = None,
    output_json: Optional[str] = None,
    error_summary: Optional[str] = None,
    logs_path: Optional[str] = None,
    root_job_id: Optional[str] = None,
) -> Job:
    job = Job(
        job_type=job_type,
        status=status,
        actor=actor,
        actor_context_json=actor_context_to_json(derive_actor_context(actor, actor_context)),
        input_json=input_json,
        output_json=output_json,
        error_summary=error_summary,
        logs_path=logs_path,
        root_job_id=root_job_id,
    )
    session.add(job)
    return job
