"""
Tests for OpenF1 tool wrappers - HTTP calls are mocked, never real.

These testa turn manual exploration into permanent, automated, network-free regression tests. They run with no dependency on OpeF1 being reachable.

httpx.AsycnClient is mocked at the point _get() uses it, so every test
here exercises the real wrapper function logic (parameter building, None-stripping, the success/failure logging split) without making an actual network call.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.tools.openf1 import (
  get_sessions, get_drivers, get_laps, get_pit_stops,
  get_stints,
  get_race_control, get_positions, get_intervals,
  TOOL_DISPATCH, TOOL_DEFINITIONS,
)

def make_mock_response(data: list):
  """
  Build a mock hhtpx.Response-like object whose .json() returns the 
  given data and whose .raise_for_status() does nothing (success_path),
  """
  mock_resp = MagicMock()
  mock_resp.json.return_value = data
  mock_resp.raise_for_status = MagicMock()
  return mock_resp

@pytest.mark.asyncio
async def test_get_sessions_returns_list(mock_openf1_sessions):
  """get_sessions returns the raw list OpenF1 provides, unmodified."""
  with patch("httpx.AsyncClient") as MockHTTP:
    instance = MockHTTP.return_value.__aenter__.return_value
    instance.get = AsyncMock(return_value=make_mock_response(mock_openf1_sessions))
    result = await get_sessions(year=2024)
  assert isinstance(result, list)
  assert result[0]["session_key"] == 9523

@pytest.mark.asyncio
async def test_get_sessions_with_country(mock_openf1_sessions):
  """get_sessions accepts an optional country_name filter"""
  with patch("httpx.AsyncClient") as MockHTTP:
    instance = MockHTTP.return_value.__aenter__.return_value
    instance.get = AsyncMock(return_value=make_mock_response(mock_openf1_sessions))
    result = await get_sessions(year=2024, country_name="Monaco")
  assert len(result) >=1

@pytest.mark.asyncio
async def test_get_drivers_uses_session_key_alone():
  """get_drivers, when given a session_key, must query by session_key ONLY"""
  captured_params = {}

  async def capture_get(url, params=None, **kwargs):
    captured_params.update(params or {})
    return make_mock_response([{"driver_number":1,"full_name":"Max VERSTAPPEN"}])
  
  with patch("httpx.AsyncClient") as MockHTTP:
    instance = MockHTTP.return_value.__aenter__.return_value
    instance.get = AsyncMock(side_effect=capture_get)
    await get_drivers(session_key=9523, year = 2024)

  assert "session_key" in captured_params
  assert "year" not in captured_params, (
    "get_drivers sent year alongside session_key"
    "(OpenF1 return 404 when both are combined)"
  )

@pytest.mark.asyncio
async def test_get_drivers_falls_back_to_year():
  """When no session_key is given, get_drivers queries by year alone."""
  captured_params={}

  async def capture_get(url, params=None, **kwargs):
    captured_params.update(params or {})
    return make_mock_response([{"driver_number":1,"full_name":"Max VERSTAPPEN"}])
  
  with patch("httpx.AsyncClient") as MockHTTP:
    instance = MockHTTP.return_value.__aenter__.return_value
    instance.get = AsyncMock(side_effect=capture_get)
    await get_drivers(year=2024)
  
  assert captured_params.get("year") == 2024
  assert "session_key" not in captured_params

@pytest.mark.asyncio
async def test_get_laps_returns_list(mock_openf1_laps):
  """get_laps returns every lap row OpenF1 provides for the filters given."""
  with patch("httpx.AsyncClient") as MockHTTP:
    instance = MockHTTP.return_value.__aenter__.return_value
    instance.get = AsyncMock(return_value=make_mock_response(mock_openf1_laps))
    result = await get_laps(session_key=9523)
  assert len(result) == 49
  assert result[0]["driver_number"] == 1

@pytest.mark.asyncio
async def test_get_laps_sends_correct_driver_number_param():
  """get_laps must sent the parameter as "driver_number"""
  captured_params ={}
  async def capture_get(url, params=None, **kwargs):
    captured_params.update(params or {})
    return make_mock_response([])
  
  with patch("httpx.AsyncClient") as MockHTTP:
    instance = MockHTTP.return_value.__aenter__.return_value
    instance.get = AsyncMock(side_effect = capture_get)
    await get_laps(session_key=9523,driver_number=1)
  
  assert "driver_number" in captured_params, (
    "get_laps did not send 'driver_number' correctly - check for typos"
  )
  assert captured_params["driver_number"] == 1

@pytest.mark.asyncio
async def test_get_pit_stops(mock_openf1_sessions):
  """get_pit_Stops returns pit lane records including pit_duration."""
  pits = [{"driver_number":1,"lap_number":22,"pit_duration":23.4}]
  with patch("httpx.AsyncClient") as MockHTTP:
    instance = MockHTTP.return_value.__aenter__.return_value
    instance.get = AsyncMock(return_value = make_mock_response(pits))
    result = await get_pit_stops(session_key=9523)
  assert result[0]["pit_duration"] == 23.4

@pytest.mark.asyncio
async def test_get_stints_returns_compound_data():
    """get_stints returns tyre compound and lap-range data per stint."""
    stints = [
        {"driver_number": 1, "stint_number": 1, "compound": "MEDIUM", "lap_start": 1, "lap_end": 32},
        {"driver_number": 1, "stint_number": 2, "compound": "HARD", "lap_start": 33, "lap_end": 78},
    ]
    with patch("httpx.AsyncClient") as MockHTTP:
        instance = MockHTTP.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=make_mock_response(stints))
        result = await get_stints(session_key=9523, driver_number=1)
    assert len(result) == 2
    assert result[0]["compound"] == "MEDIUM"
    assert result[1]["compound"] == "HARD"

@pytest.mark.asyncio
async def test_get_race_control_no_driver_filter():
    """
    get_race_control takes no driver_number parameter on purpose - race
    control messages are frequently track-wide and filtering at the API
    level would silently drop messages with no specific driver attached.
    """
    messages = [
        {"date": "2024-05-26T14:10:00", "category": "SafetyCar", "message": "SAFETY CAR DEPLOYED",
         "flag": "SC", "driver_number": None, "lap_number": 22}
    ]
    with patch("httpx.AsyncClient") as MockHTTP:
        instance = MockHTTP.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=make_mock_response(messages))
        result = await get_race_control(session_key=9523)
    assert result[0]["category"] == "SafetyCar"
    assert result[0]["driver_number"] is None

@pytest.mark.asyncio
async def test_get_positions_is_change_events_not_lap_by_lap():
    """
    get_positions returns one row per position CHANGE, not one row per
    lap - confirmed in the Day 5 docstring. A driver with no overtakes
    across a 78-lap race should have far fewer than 78 rows.
    """
    positions = [
        {"driver_number": 1, "date": "2024-05-26T13:00:00", "position": 1},
        {"driver_number": 1, "date": "2024-05-26T13:45:00", "position": 2},
    ]
    with patch("httpx.AsyncClient") as MockHTTP:
        instance = MockHTTP.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=make_mock_response(positions))
        result = await get_positions(session_key=9523, driver_number=1)
    assert len(result) == 2
    assert result[1]["position"] == 2

@pytest.mark.asyncio
async def test_get_intervals_returns_race_data():
    """get_intervals returns gap-to-leader data for a Race session."""
    intervals = [
        {"driver_number": 1, "date": "2024-05-26T13:30:00", "gap_to_leader": 0.0, "interval": None}
    ]
    with patch("httpx.AsyncClient") as MockHTTP:
        instance = MockHTTP.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=make_mock_response(intervals))
        result = await get_intervals(session_key=9523, driver_number=1)
    assert result[0]["gap_to_leader"] == 0.0

@pytest.mark.asyncio
async def test_get_intervals_propagates_404_for_non_race_sessions():
    """
    get_intervals raises HTTPStatusError for non-Race sessions, 
    it does NOT return an empty list. This test locks in that corrected understanding.
    """
    import httpx as httpx_module

    async def raise_404(url, params=None, **kwargs):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx_module.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )
        return mock_resp

    with patch("httpx.AsyncClient") as MockHTTP:
        instance = MockHTTP.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=raise_404)
        with pytest.raises(httpx_module.HTTPStatusError):
            await get_intervals(session_key=9519, driver_number=1)

@pytest.mark.asyncio
async def test_get_fails_still_logs_before_raising():
    """
    a failed call still produces a log_tool_call entry before the exception propagates, rather than silently vanishing from the audit trail.
    """
    import httpx as httpx_module

    async def raise_403(url, params=None, **kwargs):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx_module.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=MagicMock(status_code=403)
        )
        return mock_resp

    with patch("httpx.AsyncClient") as MockHTTP, \
         patch("app.tools.openf1.log_tool_call") as mock_log:
        instance = MockHTTP.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=raise_403)
        with pytest.raises(httpx_module.HTTPStatusError):
            await get_sessions(year=2024)

    mock_log.assert_called_once()
    # Confirm it logged with result_bytes=0 (no usable response on failure)
    call_args = mock_log.call_args[0]
    assert call_args[2] == 0, "Failed call should log result_bytes=0, not a real byte count"

def test_tool_dispatch_has_all_eight_tools():
    """TOOL_DISPATCH must contain exactly the 8 tools built across Days 4-5."""
    expected = {
        "get_sessions", "get_drivers", "get_laps", "get_pit_stops",
        "get_stints", "get_race_control", "get_positions", "get_intervals",
    }
    assert expected == set(TOOL_DISPATCH.keys())

def test_tool_definitions_match_dispatch_exactly():
    """
    Every tool name in TOOL_DEFINITIONS must have a matching entry in
    TOOL_DISPATCH, or agent loop will crash trying to call a
    tool Claude was told exists but can't actually execute.
    """
    definition_names = {t["name"] for t in TOOL_DEFINITIONS}
    dispatch_names = set(TOOL_DISPATCH.keys())
    assert definition_names == dispatch_names


def test_tool_definitions_have_required_schema_keys():
    """Every tool definition has the four keys Anthropic's tool-use API requires."""
    for tool in TOOL_DEFINITIONS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert "required" in tool["input_schema"]
        assert len(tool["description"]) > 10, f"{tool['name']} has a suspiciously short description"

def test_get_drivers_description_warns_about_combination_bug():
    """
    The get_drivers tool description shown to Claude must
    mention the session_key/year exclusivity rule discovered -
    this is what prevents the agent from repeating the same mistake.
    """
    get_drivers_def = next(t for t in TOOL_DEFINITIONS if t["name"] == "get_drivers")
    assert "not both" in get_drivers_def["description"].lower() or \
           "either" in get_drivers_def["description"].lower()


def test_get_intervals_description_warns_about_race_only_behavior():
    """
    The get_intervals tool description must warn that non-Race sessions
    fail with an error, not return empty data.
    """
    get_intervals_def = next(t for t in TOOL_DEFINITIONS if t["name"] == "get_intervals")
    assert "race" in get_intervals_def["description"].lower()