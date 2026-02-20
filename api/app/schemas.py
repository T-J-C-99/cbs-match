from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class CreateSessionResponse(BaseModel):
    session_id: str
    user_id: str


class AnswerInput(BaseModel):
    question_code: str
    answer_value: Any


class UpsertAnswersRequest(BaseModel):
    answers: list[AnswerInput] = Field(default_factory=list)


class SessionResponse(BaseModel):
    session: dict
    answers: dict[str, Any]


class CompleteResponse(BaseModel):
    status: str
    completed_at: datetime
    traits: dict[str, Any]
