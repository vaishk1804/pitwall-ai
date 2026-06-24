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

async def get_stints(session_key: int, driver_number: int | None = None) -> list[dict]:
  """
  Get tyre stint data for a session - which compound was used, which
  laps the stint spanned, and how worn the tyres were at the start of the stint.
  """
  params: dict[str,Any] = {"session_key": session_key}
  if driver_number:
    params["driver_number"] = driver_number
  return await _get("/stints",params)

async def get_race_control(session_key: int) -> list[dict]:
  """
  Get race control messages for a session - safety car deployments,
  flags (yellow, red, chequered), penalties, and other official incidents.
  """
  return await _get("/race_control",{"session_key":session_key})

async def get_positions(
    session_key: int,
    driver_number: int | None = None,
) -> list[dict]:
  """
  Get position data throughout a race session - every time a driver's 
  position changed, with a timestamp.

  This returns one row per position CHANGE, not one row per lap - to find the most recent row with a date at or before that moment.
  """
  params: dict[str, Any] = {"session_key": session_key}
  if driver_number:
    params["driver_number"] = driver_number
  return await _get("/position",params)

async def get_intervals(session_key: int, driver_number: int | None = None) -> list[dict]:
  """
  Get gap-to-leader and interval-to-car-ahead data for drivers during
  a race, updated approximately every 4 seconds.

  Per OpenF1's documentation, this endpoint only returns data for
  RACE sessions.
  """
  params: dict[str,Any] = {"session_key":session_key}
  if driver_number:
    params["driver_number"] = driver_number
  return await _get("/intervals",params)

# Tool manifest - defines the tools Claude can call via Anthropic's
# tool-use API. Each "description"
# filed is read directly by the model to decide which tool fits a given question,
# so wording here has a real, observable effect on which tool Claude picks.

TOOL_DEFINITIONS =[
  {
    "name": "get_sessions",
    "description": "Find F1 sessions (race, qualifying, practice) by year and optionally country. Returns session_key needed for other tools.",
    "input_schema": {
      "type": "object",
      "properties": {
        "year": {"type": "integer", "description": "Season year, e.g. 2024"},
        "country_name": {"type": "string", "description": "Optional country, e.g. 'Monaco'"},
      },
      "required": ["year"],
    },
  },
  {
    "name": "get_drivers",
    "description": "Get driver information for a session or season. Pass EITHER session_key OR year, not both - OpenF1 returns no results if both are provided together.",
    "input_schema": {
      "type": "object",
      "properties":{
      "session_key": {"type":"integer", "description": "Session key from get_sessions"},
      "year": {"type": "integer", "description": "Season year"},
    },
    "required": ["year"],
  },
  },
{
  "name": "get_laps",
  "description": "Get lap timing data including sector times and compound for a session. Requires session_key.",
  "input_schema": {
    "type": "object",
    "properties": {
      "session_key": {"type":"integer"},
      "driver_number": {"type":"integer", "description": "Optional - filter to one driver"},
      "lap_number": {"type": "integer", "description": "Optional - filter to one lap"},
    },
    "required": ["session_key"],
  },
},
{
  "name": "get_pit_stops",
  "description": "Get pit stop records including lap number and pit duration.",
  "input_schema":{
    "type": "object",
    "properties": {
      "session_key": {"type":"integer"},
      "driver_number": {"type":"integer","description":"Optional"},
    },
    "required": ["session_key"],
  },
},
{
   "name": "get_stints",
        "description": "Get tyre stint data - compound, stint number, lap ranges.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_key": {"type": "integer"},
                "driver_number": {"type": "integer", "description": "Optional"},
            },
            "required": ["session_key"],
        },
},
 {
        "name": "get_race_control",
        "description": "Get race director messages, safety car periods, flags, and penalties for a session.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_key": {"type": "integer"},
            },
            "required": ["session_key"],
        },
    },
    {
        "name": "get_positions",
        "description": "Get position-change events for a session, not lap-by-lap positions. Use to find when overtakes happened.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_key": {"type": "integer"},
                "driver_number": {"type": "integer", "description": "Optional"},
            },
            "required": ["session_key"],
        },
    },
    {
        "name": "get_intervals",
        "description": "Get gap-to-leader and interval data for drivers during a race. Only works for Race sessions - calling this with a Qualifying or Practice session_key will fail with an error, not return empty data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_key": {"type": "integer"},
                "driver_number": {"type": "integer", "description": "Optional"},
            },
            "required": ["session_key"],
        },
    },
]

# Maps each tool name to its actula Python function. The agent loop
# recieves a tool_use block from Calude containing a "name" string
# and looks it up here to find which function to
# actually call

TOOL_DISPATCH ={
  "get_sessions": get_sessions,
  "get_drivers": get_drivers,
  "get_laps": get_laps,
  "get_pit_stops": get_pit_stops,
  "get_stints": get_stints,
  "get_race_control": get_race_control,
  "get_positions": get_positions,
  "get_intervals": get_intervals,
}
