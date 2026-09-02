import json
from typing import Any, Optional

import redis.asyncio as redis


class RedisCache:
  """Thin wrapper around redis-py to manage JSON payloads."""

  def __init__(self, url: Optional[str]):
    self.url = url
    self.client = redis.from_url(url, encoding="utf-8", decode_responses=True) if url else None

  async def get_json(self, key: str) -> Optional[Any]:
    if not self.client:
      return None
    payload = await self.client.get(key)
    if payload is None:
      return None
    return json.loads(payload)

  async def set_json(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
    if not self.client:
      return
    await self.client.set(key, json.dumps(value), ex=ttl_seconds)

  async def close(self) -> None:
    if self.client:
      await self.client.aclose()
