import asyncio
import sys
import os

# Local Docker services
os.environ.setdefault("POSTGRES_DSN", "postgresql://whodba:whopass@localhost:5433/who_eats_whom")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "testpass")
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")

if sys.platform == "win32":
  asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())