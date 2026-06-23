"""
SQLAlchemy ORM models for PitWall AI.

Four tables form the audit trail for every interaction with the system:

Session 
  - one analysis session, can have many Query rows.

Query 
  - one questions asked.
  - Belongs to one Session. 
  - Has at most one Response.
  - Can trigger many ToolCallLog rows.

Response 
  - holds the actual answer, confidence scores, sources and fallback info.

ToolCallLog 
  - an audit row for every single OpenF1 call.
"""
from datetime import datetime, timezone
from sqlalchemy import (
  String, Text, Float, Integer, DateTime, JSON,
  ForeignKey, Enum as SAEnum, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.core.database import Base

class QueryStatus(str, enum.Enum):
  """
  Lifecycle states for a Query.

  State transitions in practice:
    pending    -> processing  (Celery worker picks up the task, or sync
    endpoint starts calling the agent)
    processing -> complete    (agent returned a usable answer)
    processing -> no_data     (agent's fallback_triggered=True; no
    grounding data was found)
    processing -> failed      (an unhandled exception occurred)
  """
  pending="pending"
  processing="processing"
  complete="complete"
  failed="failed"
  no_data="no_data"

class ChatSession(Base):
  """
  One analysis session - the container for a sequence of related questions.
  """
  __tablename__ = "sessions"

  id: Mapped[str] = mapped_column(String(36), primary_key=True)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
  )
  # Arbitrary shared context for this session
  context: Mapped[dict] = mapped_column(JSON, default=dict)
  queries: Mapped[list["Query"]] = relationship(back_populates="session")

class Query(Base):
  """
  One question asked by the user, optionally scoped to a ChatSession.
  """
  __tablename__ = "queries"
  id: Mapped[str] = mapped_column(String(36),primary_key=True)

  #Nullable: a Query may not belong to any ChatSession
  session_id: Mapped[str | None] = mapped_column(
    ForeignKey("sessions.id"), nullable=True,index=True
  )

  user_query: Mapped[str] = mapped_column(Text)
  status: Mapped[QueryStatus]= mapped_column(
    SAEnum(QueryStatus), default = QueryStatus.pending, index = True
  )
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
  )

  # Set when a Query is dispatched to Celery for async processing.
  # Indexed so the worker/poller can look up " which Query does this
  # Celery task ID belong to" without a full table scan.
  celery_task_id: Mapped[str | None] = mapped_column(
    String(36), nullable=True, index=True
  )
  session: Mapped["ChatSession | None"] = relationship(back_populates="queries")

  # useList=False: a Query has at most one Response, not a list of them.
  # cascade="all, delete-orphan": deleting a Query deletes its Response too,
  # so no orphaned answer rows are left pointing at a missing query_id.
  response: Mapped["Response | None"] = relationship(
    back_populates="query",
    uselist=False,
    cascade="all, delete-orphan",
  )

  tool_calls: Mapped[list["ToolCallLog"]] = relationship(
    back_populates="query",
    cascade="all, delete-orphan",
  )

class Response(Base):
  """
  The answer for exactly one Query.
  """
  __tablename__ = "responses"

  id: Mapped[str] = mapped_column(String(36), primary_key=True)

  # unique=True enforces one Response per Query at the database level.
  query_id: Mapped[str] = mapped_column(ForeignKey("queries.id"),unique=True)
  
  answer: Mapped[str] = mapped_column(Text)
  confidence: Mapped[float] = mapped_column(Float,default=0.0)

  # [{tool, summary,url, row_count}, ...] - see app.models.schemas.Source
  sources: Mapped[list] = mapped_column(JSON, default=list)

  reasoning_steps: Mapped[list] = mapped_column(JSON, default=list)
  fallback_triggered: Mapped[bool] = mapped_column(default=False)
  fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

  latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
  prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
  completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), default = lambda: datetime.now(timezone.utc)
  )
  query: Mapped["Query"] = relationship(back_populates="response")

class ToolCallLog(Base):
  """
  One audit row per OpenF1 API call made while answering a Query.
  
  Many rows can belong to a single Query (e.g. get_sessions, then
  get_laps, then get_rac_control all in service of one question).
  """
  __tablename__="tool_call_logs"
  id: Mapped[str] = mapped_column(String(36), primary_key=True)
  query_id: Mapped[str] = mapped_column(ForeignKey("queries.id"))

  tool_name: Mapped[str] = mapped_column(String(64))
  tool_args: Mapped[dict] = mapped_column(JSON, default=dict)

  result_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
  result_row_count: Mapped[int] = mapped_column(Integer, default=0)
  latency_ms: Mapped[float] = mapped_column(Float, default=0.0)

  created_At: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
  )
  query: Mapped["Query"] = relationship(back_populates="tool_calls")

# composite index: the most common real query pattern is "all queries for 
# session X , most recent first"
Index("ix_queries_session_id_created_at"), Query.session_id, Query.created_at