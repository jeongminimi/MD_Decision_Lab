from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from .contracts import ContentDraft, DraftSaveRequest, ProductContentBrief, SavedDraft, SavedDraftSummary
from .models import SavedContentDraft
from .service import create_draft


router = APIRouter(prefix="/api/shortform/v1", tags=["Short-form drafts"])


def _saved(record: SavedContentDraft) -> SavedDraft:
    return SavedDraft(
        id=record.id, product_name=record.product_name,
        brief=ProductContentBrief.model_validate(record.brief),
        draft=ContentDraft(
            hook=record.hook, script_beats=record.script_beats, caption=record.caption,
            call_to_action=record.call_to_action, review_note=record.review_note,
        ),
        created_at=record.created_at, updated_at=record.updated_at,
    )


@router.post("/draft", response_model=ContentDraft)
def generate_draft(brief: ProductContentBrief):
    return create_draft(brief)


@router.get("/drafts", response_model=list[SavedDraftSummary])
def list_drafts(db: Session = Depends(get_db)):
    records = db.scalars(select(SavedContentDraft).order_by(SavedContentDraft.updated_at.desc(), SavedContentDraft.id.desc()).limit(50)).all()
    return [SavedDraftSummary(id=item.id, product_name=item.product_name, hook=item.hook, updated_at=item.updated_at) for item in records]


@router.get("/drafts/{draft_id}", response_model=SavedDraft)
def get_draft(draft_id: int, db: Session = Depends(get_db)):
    record = db.get(SavedContentDraft, draft_id)
    if record is None:
        raise HTTPException(status_code=404, detail="저장된 초안을 찾지 못했습니다.")
    return _saved(record)


@router.post("/drafts", response_model=SavedDraft, status_code=201)
def save_draft(payload: DraftSaveRequest, db: Session = Depends(get_db)):
    record = SavedContentDraft(product_name=payload.brief.product_name)
    _update(record, payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    return _saved(record)


@router.put("/drafts/{draft_id}", response_model=SavedDraft)
def update_draft(draft_id: int, payload: DraftSaveRequest, db: Session = Depends(get_db)):
    record = db.get(SavedContentDraft, draft_id)
    if record is None:
        raise HTTPException(status_code=404, detail="저장된 초안을 찾지 못했습니다.")
    _update(record, payload)
    db.commit()
    db.refresh(record)
    return _saved(record)


def _update(record: SavedContentDraft, payload: DraftSaveRequest):
    record.product_name = payload.brief.product_name
    record.brief = payload.brief.model_dump()
    record.hook = payload.draft.hook
    record.script_beats = payload.draft.script_beats
    record.caption = payload.draft.caption
    record.call_to_action = payload.draft.call_to_action
    record.review_note = payload.draft.review_note
