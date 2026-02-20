import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from .database import Base


class SurveySession(Base):
    __tablename__ = "survey_session"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    survey_slug = Column(String, nullable=False)
    survey_version = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="in_progress")
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class SurveyAnswer(Base):
    __tablename__ = "survey_answer"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("survey_session.id", ondelete="CASCADE"), nullable=False)
    question_code = Column(String, nullable=False)
    answer_value = Column(JSONB, nullable=False)
    answered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("session_id", "question_code", name="uq_session_question"),
        Index("idx_survey_answer_session_id", "session_id"),
        Index("idx_survey_answer_question_code", "question_code"),
    )


class UserTraits(Base):
    __tablename__ = "user_traits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False)
    survey_slug = Column(String, nullable=False)
    survey_version = Column(Integer, nullable=False)
    traits = Column(JSONB, nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "survey_slug", "survey_version", name="uq_user_traits_version"),
        Index("idx_user_traits_user_id", "user_id"),
    )
