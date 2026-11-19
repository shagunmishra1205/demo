"""Optional progress saving. Used only when the user chooses to save.
Sensitive answers (Aadhaar, PAN etc.) are never stored. Sessions expire after the TTL."""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SavedSession
from ..schemas import SessionCreated, SessionIn, SessionOut

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _purge_expired(db: Session) -> None:
    db.execute(delete(SavedSession).where(SavedSession.expires_at < datetime.now(timezone.utc)))
    db.commit()


def _strip_sensitive(body: SessionIn) -> dict:
    sensitive_ids = {f.id for f in body.form.fields if f.type == "sensitive"}
    return {k: v for k, v in body.answers.items() if k not in sensitive_ids}


@router.post("", response_model=SessionCreated, status_code=201)
def save_session(body: SessionIn, db: Session = Depends(get_db)):
    _purge_expired(db)
    row = SavedSession(
        form_json=body.form.model_dump_json(),
        answers_json=json.dumps(_strip_sensitive(body), ensure_ascii=False),
        idx=body.idx,
        lang=body.lang,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return SessionCreated(id=row.id, expires_at=row.expires_at)


@router.get("/{session_id}", response_model=SessionOut)
def load_session(session_id: str, db: Session = Depends(get_db)):
    _purge_expired(db)
    row = db.get(SavedSession, session_id)
    if not row:
        raise HTTPException(404, "Saved progress not found or expired")
    return SessionOut(
        id=row.id,
        form=json.loads(row.form_json),
        answers=json.loads(row.answers_json),
        idx=row.idx,
        lang=row.lang,
        expires_at=row.expires_at,
    )


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, db: Session = Depends(get_db)):
    row = db.get(SavedSession, session_id)
    if row:
        db.delete(row)
        db.commit()
