from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ProductContentBrief(BaseModel):
    product_name: str = Field(min_length=1, max_length=160)
    key_feature: str = Field(min_length=1, max_length=500)
    audience: str = Field(default="", max_length=200)
    offer: str = Field(default="", max_length=300)
    action_context: str = Field(default="", max_length=300)
    tone: str = Field(default="친근하고 구체적인", max_length=80)


class ContentDraft(BaseModel):
    hook: str = Field(min_length=1, max_length=1000)
    script_beats: list[str] = Field(min_length=1, max_length=12)
    caption: str = Field(min_length=1, max_length=5000)
    call_to_action: str = Field(min_length=1, max_length=1000)
    review_note: str = Field(default="", max_length=2000)

    @field_validator("hook", "caption", "call_to_action")
    @classmethod
    def required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("필수 문구는 비워둘 수 없습니다.")
        return value

    @field_validator("script_beats")
    @classmethod
    def required_beats(cls, value: list[str]) -> list[str]:
        if any(not beat.strip() or len(beat) > 1000 for beat in value):
            raise ValueError("각 영상 흐름은 1~1000자로 입력하세요.")
        return value


class DraftSaveRequest(BaseModel):
    brief: ProductContentBrief
    draft: ContentDraft


class SavedDraft(BaseModel):
    id: int
    product_name: str
    brief: ProductContentBrief
    draft: ContentDraft
    created_at: datetime
    updated_at: datetime


class SavedDraftSummary(BaseModel):
    id: int
    product_name: str
    hook: str
    updated_at: datetime
