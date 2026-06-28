"""
Shared pytest fixtures for PitWall AI's test suite.

    test_engine  - session-scoped, file-based SQLite engine shared by
                   every test in the run. File-based (not :memory:) on
                   purpose: an in-memory SQLite database only exists for
                   the lifetime of one connection - a file on disk is
                   visible to every connection that opens it, which
                   matters once FastAPI's TestClient is introduced in
                   Sprint 2 and opens its own separate connection.

    db_session   - function-scoped session wrapped in its own
                   transaction that is rolled back after each test.
                   This guarantees test isolation: a ChatSession row
                   created in one test never leaks into the next test.
"""

import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.db import ChatSession, Query, Response, ToolCallLog, QueryStatus


TEST_DB_URL = "sqlite:///./test.db"


@pytest.fixture(scope="session")
def test_engine():
    """
    Single engine for the entire test session.

    Tables are created once at the start of the session and dropped
    once at the end; the .db file itself is also removed afterward so
    it never gets committed or confused with a real database file.
    """
    eng = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    import os
    try:
        os.remove("./test.db")
    except (FileNotFoundError, PermissionError):
        pass


@pytest.fixture(scope="function")
def db_session(test_engine):
    """
    Per-test database session, wrapped in a transaction that is rolled
    back after the test completes - whether it passed or failed.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection)
    session = TestSession()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def sample_session(db_session) -> ChatSession:
    """A pre-created ChatSession row, scoped to Monaco 2024."""
    s = ChatSession(id=str(uuid.uuid4()), context={"year": 2024})
    db_session.add(s)
    db_session.commit()
    return s


@pytest.fixture
def sample_query(db_session, sample_session) -> Query:
    """A pre-created Query row belonging to sample_session, status=pending."""
    q = Query(
        id=str(uuid.uuid4()),
        session_id=sample_session.id,
        user_query="Who had the fastest lap at Monaco 2024?",
        status=QueryStatus.pending,
    )
    db_session.add(q)
    db_session.commit()
    return q


@pytest.fixture
def sample_response(db_session, sample_query) -> Response:
    """A pre-created Response row for sample_query, marking it complete."""
    r = Response(
        id=str(uuid.uuid4()),
        query_id=sample_query.id,
        answer="Charles Leclerc set the fastest lap at Monaco 2024.",
        confidence=0.87,
        sources=[{"tool": "get_laps", "summary": "Retrieved 78 laps", "url": None, "row_count": 78}],
        reasoning_steps=["Called get_sessions", "Called get_laps"],
        fallback_triggered=False,
        latency_ms=1420.5,
        prompt_tokens=800,
        completion_tokens=250,
    )
    sample_query.status = QueryStatus.complete
    db_session.add(r)
    db_session.commit()
    return r


@pytest.fixture
def mock_analyst_response():
    """
    A realistic AnalystResponse object for tests that need a believable
    agent output without making a real Anthropic API call.
    """
    from app.models.schemas import AnalystResponse, Source
    return AnalystResponse(
        answer="Lando Norris led from lap 15 after a VSC period.",
        confidence=0.85,
        reasoning_steps=["Called get_sessions", "Called get_laps", "Called get_race_control"],
        sources=[
            Source(tool="get_sessions", summary="Found Monaco 2024 Race session", row_count=1),
            Source(tool="get_laps", summary="Retrieved 78 laps", row_count=78),
        ],
        fallback_triggered=False,
        suggested_followups=["What was Norris's average lap time?", "When did Verstappen pit?"],
    )


@pytest.fixture
def mock_openf1_sessions():
    """A realistic /sessions response shape, frozen for deterministic tests."""
    return [
        {
            "session_key": 9523,
            "session_name": "Race",
            "session_type": "Race",
            "country_name": "Monaco",
            "year": 2024,
            "date_start": "2024-05-26T13:00:00",
        }
    ]


@pytest.fixture
def mock_openf1_laps():
    """A realistic /laps response shape: 49 laps for one driver."""
    return [
        {
            "driver_number": 1,
            "lap_number": i,
            "lap_duration": 74.5 + (i * 0.01),
            "duration_sector_1": 24.1,
            "duration_sector_2": 28.4,
            "duration_sector_3": 22.0,
            "is_pit_out_lap": False,
            "compound": "MEDIUM",
        }
        for i in range(1, 50)
    ]