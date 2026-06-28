"""
Tests for the database layer - pure SQLAlchemy, no HTTP involved.
"""
import uuid
import pytest
from app.models.db import ChatSession, Query, Response, ToolCallLog, QueryStatus

def test_create_retrieve_session(db_session):
  """A ChatSession can be created and its JSON context retrieved unchanged."""
  s = ChatSession(id=str(uuid.uuid4()),context={"year":2024})
  db_session.add(s)
  db_session.commit()
  retrieved = db_session.get(ChatSession, s.id)
  assert retrieved is not None
  assert retrieved.context["year"] == 2024

def test_query_links_to_session(db_session, sample_session):
  """A Query correctly stores the session_id of its parent ChatSession."""
  q = Query(
    id=str(uuid.uuid4()),
    session_id=sample_session.id,
    user_query="Test question",
    status=QueryStatus.pending,
  )
  db_session.add(q)
  db_session.commit()
  assert q.session_id == sample_session.id

def test_query_status_transitions(db_session, sample_query):
  sample_query.status = QueryStatus.processing
  db_session.commit()
  refreshed = db_session.get(Query, sample_query.id)
  assert refreshed.status == QueryStatus.processing

  refreshed.status = QueryStatus.complete
  db_session.commit()
  final = db_session.get(Query, sample_query.id)
  assert final.status == QueryStatus.complete

def test_response_links_to_query(db_session, sample_query):
  """A Response correctly stores the query_id of the Query it answers."""
  r = Response(
    id=str(uuid.uuid4()),
    query_id = sample_query.id,
    answer="Test answer",
    confidence = 0.7,
    sources=[],
    reasoning_steps=["Step 1"],
    fallback_triggered=False,
  )
  db_session.add(r)
  db_session.commit()
  assert r.query_id == sample_query.id

def test_response_confidence_stored(db_session, sample_query):
  r = Response(
    id = str(uuid.uuid4()),
    query_id= sample_query.id,
    answer="Answer",
    confidence=0.83,
    sources=[],
  )
  db_session.add(r)
  db_session.commit()
  retrieved = db_session.get(Response, r.id)
  assert abs(retrieved.confidence - 0.83) < 0.001

def test_response_fallback_fields(db_session,sample_query):
  """fallback_triggered and fallback_reason are stored together correctly."""
  r = Response(
    id=str(uuid.uuid4()),
    query_id=sample_query.id,
    answer="No data found.",
    confidence=0.05,
    fallback_triggered=True,
    fallback_reason = "No session matched year=1990",
    sources=[],
  )
  db_session.add(r)
  db_session.commit()
  retrieved = db_session.get(Response,r.id)
  assert retrieved.fallback_triggered is True
  assert "1990" in retrieved.fallback_reason

def test_sources_stored_as_json(db_session, sample_query):
  """The sources list round-trips through the JSON column unchanged."""
  sources =[{"tool":"get_laps","summary":"78 laps", "url": None, "row_count": 78}]
  r = Response(
    id=str(uuid.uuid4()),
    query_id=sample_query.id,
    answer="Answer",
    confidence=0.8,
    sources=sources,
  )
  db_session.add(r)
  db_session.commit()
  retrieved = db_session.get(Response, r.id)
  assert len(retrieved.sources) == 1
  assert retrieved.sources[0]["tool"] == "get_laps"

def test_reasoning_steps_stored(db_session, sample_query):
  """reasoning_steps, al list of strings, round-trips through the JSON column."""
  steps = ["Called get_session","Got session_key=9523","Called get_laps"]
  r = Response(
    id=str(uuid.uuid4()),
    query_id=sample_query.id,
    answer="Answer",
    confidence=0.8,
    reasoning_steps=steps,
    sources=[],
  )
  db_session.add(r)
  db_session.commit()
  retrieved = db_session.get(Response, r.id)
  assert len(retrieved.reasoning_steps) == 3
