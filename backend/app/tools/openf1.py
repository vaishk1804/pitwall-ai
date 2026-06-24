"""
OpenF1 API tool wrappers.

Each function below fetches one OpenF1 resource type and returns the raw JSON response as a list of dicts. These wrappers are the "tools"
the Claude agent will cann via Anthropic's tool-use API -
TOOL_DEFINITIONS describes them to Claude, and
TOOL_DISPATCH maps tool names back to these functions so 
the agent loop can actually execute them.

API reference: hhtps://openf1.org/docs/

Every call - successful or failed - is timed and logged via log_tool_call().
"""

import httpx
import time
from typing import Any 
from app.core.config import get_settings
from app.core.logging import log_tool_call

BASE = "https://api.openf1.org/v1"
TIMEOUT = 15.0

async def _get(path: str, params: dict) -> list[dict]:
  """
  Shared GET helped for every OpenF1 endpoint.

  Strips out any parameter whose value is None before sending the request.
  """
  url=f"{BASE}{path}"
  t0 = time.perf_counter()
  try:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
      r = await client.get(url, params={k: v for k,v in params.items() if v is not None})
      r.raise_for_status()
      data = r.json()
  except Exception:
    latency = (time.perf_counter()-t0) * 1000
    log_tool_call(path, params, 0 , latency)
    raise

  latency = (time.perf_counter()-t0) * 1000
  log_tool_call(path, params, len(str(data)), latency)
  return data if isinstance(data, list) else [data]

async def get_sessions(year: int = 2024, country_name: str | None = None) -> list[dict]:
  """
  Get race weekend sessions (Practice, Qualifying, Sprint, Race) for a 
  given year, optionally filtered to one country/Grand Prix.

  This is the entry-point tool: almost every other OpenF1 endpoint
  required a session key. The system prompt instructs Claude to call this tool first in every workflow.
  """
  params = {"year": year}
  if country_name:
    params["country_name"] = country_name
  return await _get("/sessions", params)

async def get_drivers(session_key: int | None = None, year: int = 2024) -> list[dict]:
  """
  Get driver identity and team info for a specific session, or for an entire season if only year is given.

  session_key and year are alternate query modes.
  """
  if session_key:
    return await _get("/drivers",{"session_key":session_key})
  return await _get("/drivers",{"year":year})


async def get_laps(
    session_key: int,
    driver_number: int | None = None,
    lap_number: int | None = None,
) -> list[dict]:
  """
  Get lap timing data for a session - sector times
  """
  params: dict[str,Any] = {"session_key": session_key}
  if driver_number:
    params["driver_number"] = driver_number
  if lap_number:
    params["lap_number"] = lap_number
  return await _get("/laps",params)

async def get_pit_stops(session_key: int, driver_number: int | None = None) -> list[dict]:
  """
  Get pit stop records for a session: which lap, and how long the stop took.
  """
  params: dict[str, Any] = {"session_key": session_key}
  if driver_number:
    params["driver_number"] = driver_number
  return await _get("/pit",params)