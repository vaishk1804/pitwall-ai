#app/core/logging.py
import logging
import json
import time
from datetime import datetime, timezone

logger = logging.getLogger("pitwall")


def setup_logging(level: str = "INFO") -> None:
  logging.basicConfig(
    level=getattr(logging, level.upper()),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
  )

def log_llm_call(
    query: str,
    context_tokens: int,
    tools_used: list[str],
    response_summary: str,
    confidence: float,
    latency_ms: float,
    session_id: str | None = None,
) -> None:
  """Structured log for every LLM interaction - no silent calls."""
  entry={
    "event":"llm_call",
    "ts": datetime.now(timezone.utc).isoformat(),
    "session_id": session_id,
    "query_preview": query[:120],
    "context_tokens": context_tokens,
    "tools_used": tools_used,
    "response_preview": response_summary[:120],
    "confidence": confidence,
    "latency_ms": round(latency_ms),
  }
  logger.info(json.dumps(entry))

def log_tool_call(
    tool_name: str,
    args: dict,
    result_size: int,
    latency_ms: float,
) -> None:
  entry = {
    "event": "tool_call",
    "ts": datetime.now(timezone.utc).isoformat(),
    "tool":tool_name,
    "args": args,
    "result_bytes": result_size,
    "latency_ms": round(latency_ms,1),
  }
  logger.info(json.dumps(entry))

def log_fallback(
    reason: str,
    query: str,
    session_id: str | None = None,
) -> None:
  entry = {
    "event": "llm_fallback",
    "ts": datetime.now(timezone.utc).isoformat(),
    "session_id": session_id,
    "reason": reason,
    "query_preview": query[:120],
  }
  logger.warning(json.dumps(entry))