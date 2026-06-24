"""
Pydantic schemas for PitWall AI.

This file defines three distinct contracts.

  1. OpenF1 raw shape
      Typed representation of what the OpenF1 API actually returns. These document the external data contract this project depends on.
  
  2. LLM output contract ( Source, AnalystResponse)
      The structured schema Claude must return on every call. Confidence is bounded at the schema level, fallback state is a required first-class filed, and sources are typed nested objects rather than free-tex the model could hallucinate into anything.

  3. API request/response shapes
      What the FastAPI endpoints actually accept and return. Decouple so the public API contract stays stable even if LLM-facing schema or the internal databse enum changes shape later.
"""

from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime

# -- OpenF1 raw shapes

class DriverInfo(BaseModel):
  """One driver's identity and team info for a given session or season."""
  driver_number: int
  broadcast_name: str
  full_name: str
  name_acronym: str
  team_name: str
  country_code: str | None = None
  headshot_url: str | None = None

class LapData(BaseModel):
  """
  Timing data for a single lap by a single driver.

  lap_duration and the three sector times are nullable because OpenF1
  omits them for incomplete laps
  """
  driver_number: int
  lap_number: int
  lap_duration: float | None = None
  duration_sector_1: float | None = None
  duration_sector_2: float | None = None
  duration_sector_3: float | None = None
  is_pit_out_lap: bool = False
  compound: str | None = None

class PitStop(BaseModel):
  """One pit stop event: which lap it happened on and how long it took."""
  driver_number: int
  lap_number: int
  pit_duration: float | None = None

class Position(BaseModel):
  """A driver's race position at a given timestamp."""
  driver_number: int
  date: str
  position: int

class RaceControlMessage(BaseModel):
  """
  A race control event - safety car deployment, flags, penalties, etc.
  """
  date: str
  category: str
  message: str
  flag: str | None = None
  driver_number: int | None = None
  lap_number: int | None = None

# --- LLM output contract ----
# This is the schema Claude is instructed 
# to return as a raw JSON on every call. Pydantic validates it the moment
# it is constructed - malformed model output never silently reaches
# the database or the frontend

class Source(BaseModel):
  """
  One data source the agent consulted while answering a question.

  Used as a typed, nested object inside AnalystResponse.sources rather
  that a free-text string - this means the model cannot describe a source in vague or misleading prose; it must populate these specific ,
  auditable fields (which tool, how many rows, what URL).
  """
  tool: str = Field(description="Which OpenF1 endpoint this data came from")
  summary: str = Field(description="One sentence describing what data was retrieved")
  url: str | None = Field(default=None, description="API URL used")
  row_count: int = Field(default=0, description="How many rows were returned")

class AnalystResponse(BaseModel):
  """
  Structured output Claude must return. Never treated as ground truth without validation.

  Design notes on each field:
    - confidence is bounded to [0,1] via Field(ge=0.0, le=1.0). This 
    is the first line of defense against malformed model output - 
    Pydantic rejects an out-of-range value (e.g. 1.5) immediately,
    before the agent's own confidence-derivation logic even runs.
    - fallback_triggered / fallback_reason are a required pair, not an
    optional extra. This is the literal mechanism behind "make
    fallbacks explicit in theUI" - when fallback_triggered is True,
    the frontend renders a visible warning banner using fallback_reason as the explanation.
    - sources is a list of the typed Source model above.
  """
  answer: str = Field(description="Full analyst answer in markdown")
  confidence: float = Field(
    ge=0.0, le=1.0,
    description="0-1 confidence that the answer is grounded in retrieved data. 0 = no data found, 1 = direct data match."
  )
  reasoning_steps: list[str] = Field(
    default_factory=list,
    description="Chain of thought steps Claude took before answering"
  )
  sources: list[Source] = Field(
    default_factory=list,
    description="Each data source consulted"
  )
  fallback_triggered: bool = Field(
    default=False,
    description="True if no relevant F1 data was found and Claude had to decline or estimate"
  )
  fallback_reason: str | None = Field(
    default=None,
    description="If fallback_triggered, explains why data was unavailable"
  )
  suggested_followups: list[str] = Field(
    default_factory=list,
    description="2-3 related questions the user might want to ask next"
  )

# -- API request / response shapes ----
# What the FastAPI layer actually acepts and 
# returns. Kept seperate from AnalystResponse so the public API contract
# can stay stable even as the LLM-facing schema is tuned.

class QueryRequest(BaseModel):
  """
  Incoming request body for POST /queries/.

  question has min_length/max_length so garbage input is rejected before
  it ever reaches Claude, saving a wasted API call and giving the user immediate
  feedback instead of a confusing downstream error.
  """
  question: str = Field(min_length=3, max_length=500)
  session_id: str | None = None
  context: dict = Field(default_factory=dict)    # optional {year, round, driver}

class QueryResponse(BaseModel):
  """
  Outgoing response body for the query endpoints.

  status uses Literal[...] rather than importing QueryStatus from
  app.model.db - this keeps the public API contract decouple from the internal database enum.
  """
  query_id: str
  status: Literal["pending","processing","complete","failed","no_data"]
  answer: str | None = None
  confidence: float | None = None
  sources: list[Source] = []
  reasoning_steps: list[str] = []
  fallback_triggered: bool = False
  fallback_reason: str | None = None
  suggested_followups: list[str] = []
  latency_ms: float | None = None
  prompt_tokens: int | None = None
  completion_tokens: int | None = None
  created_at: datetime | None = None

class SessionCreate(BaseModel):
  """Request body for POST /sessions/ - creating a new ChatSession"""
  context: dict = Field(default_factory=dict)

class SessionResponse(BaseModel):
  """Response body returned after creating or fetching a ChatSession"""
  id: str
  created_at: datetime
  context: dict