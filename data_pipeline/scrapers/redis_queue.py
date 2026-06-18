"""
ASIM-Tracker: Redis Ingestion Queue Buffer
Implements thread-safe, non-blocking asynchronous queue buffers for streaming
financial alternative feeds and raw order book ticks.
Features automatic in-memory fallback if Redis is unavailable.
"""

import json
import logging
import time
from typing import Any, Dict, Optional
import asyncio

import redis.asyncio as aioredis

import config

logger = logging.getLogger("asim_tracker.redis_queue")


class RedisQueueClient:
    """
    Asynchronous connection client managing queues for news feeds and market ticks.
    Automatically falls back to local in-memory queues if Redis connection fails.
    """

    def __init__(self) -> None:
        self.host = config.REDIS_HOST
        self.port = config.REDIS_PORT
        self.password = config.REDIS_PASSWORD
        self.db = config.REDIS_DB

        self.pool: Optional[aioredis.ConnectionPool] = None
        self.redis: Optional[aioredis.Redis] = None
        self.mock_mode = False

        # Local in-memory queues for fallback mock mode
        self._mock_news_queue: asyncio.Queue = asyncio.Queue()
        self._mock_tick_queues: Dict[str, asyncio.Queue] = {}

    async def connect(self) -> bool:
        """
        Initializes the connection pool and verifies connection to the Redis server.
        Activates in-memory mock mode if connection fails.
        """
        if self.mock_mode:
            return False

        try:
            self.pool = aioredis.ConnectionPool(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            self.redis = aioredis.Redis(connection_pool=self.pool)
            # Test connection
            await self.redis.ping()
            logger.info(f"Connected to Redis queue database at {self.host}:{self.port}")
            self.mock_mode = False
            return True
        except Exception as e:
            logger.warning(
                f"Could not connect to Redis at {self.host}:{self.port} ({e}). "
                "Activating in-memory mock queue fallback."
            )
            self.mock_mode = True
            if self.pool:
                await self.pool.disconnect()
            self.redis = None
            self.pool = None
            return False

    async def ping(self) -> bool:
        """
        Pings the Redis server. Returns False if in mock mode or if connection is lost.
        """
        if self.mock_mode or not self.redis:
            return False
        try:
            return await self.redis.ping()
        except Exception:
            return False

    async def push_news(self, ticker: str, text: str, sentiment: float = 0.0) -> int:
        """
        Pushes a news item dictionary into the news queue.
        """
        item = {
            "timestamp": int(time.time() * 1000),
            "ticker": ticker.strip().upper(),
            "text": text.strip(),
            "sentiment": float(sentiment),
        }
        serialized = json.dumps(item)

        if self.mock_mode or not self.redis:
            await self._mock_news_queue.put(serialized)
            return 1

        try:
            # RPUSH to append to the end of the list (FIFO queue)
            # LTRIM keeps the queue size bounded to prevent memory issues
            key = "asim:queue:news"
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.rpush(key, serialized)
                pipe.ltrim(key, -1000, -1)
                results = await pipe.execute()
            return int(results[0])
        except Exception as e:
            logger.error(f"Redis news push failed: {e}. Falling back to mock queue.")
            await self._mock_news_queue.put(serialized)
            return 1

    async def pop_news(self) -> Optional[Dict[str, Any]]:
        """
        Pops the oldest news item from the news queue.
        """
        serialized: Optional[str] = None

        if self.mock_mode or not self.redis:
            try:
                # Non-blocking check for local queue
                serialized = self._mock_news_queue.get_nowait()
                self._mock_news_queue.task_done()
            except asyncio.QueueEmpty:
                return None
        else:
            try:
                # LPOP retrieves and removes from the head of the list (FIFO queue)
                serialized = await self.redis.lpop("asim:queue:news")
            except Exception as e:
                logger.error(f"Redis news pop failed: {e}. Checking mock queue.")
                try:
                    serialized = self._mock_news_queue.get_nowait()
                    self._mock_news_queue.task_done()
                except asyncio.QueueEmpty:
                    return None

        if not serialized:
            return None

        try:
            return json.loads(serialized)
        except Exception as e:
            logger.error(f"Failed to deserialize news item: {e}")
            return None

    async def push_tick(
        self, ticker: str, price: float, volume: float, bid_vol: float, ask_vol: float
    ) -> int:
        """
        Pushes a market tick dictionary into the ticker-specific queue.
        """
        ticker_key = ticker.strip().upper()
        item = {
            "timestamp": int(time.time() * 1000),
            "ticker": ticker_key,
            "price": float(price),
            "volume": float(volume),
            "bid_vol": float(bid_vol),
            "ask_vol": float(ask_vol),
        }
        serialized = json.dumps(item)

        if self.mock_mode or not self.redis:
            if ticker_key not in self._mock_tick_queues:
                self._mock_tick_queues[ticker_key] = asyncio.Queue()
            await self._mock_tick_queues[ticker_key].put(serialized)
            return 1

        try:
            key = f"asim:queue:ticks:{ticker_key}"
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.rpush(key, serialized)
                pipe.ltrim(key, -500, -1)  # Bounded size for tick queues
                results = await pipe.execute()
            return int(results[0])
        except Exception as e:
            logger.error(f"Redis tick push failed for {ticker_key}: {e}. Falling back to mock queue.")
            if ticker_key not in self._mock_tick_queues:
                self._mock_tick_queues[ticker_key] = asyncio.Queue()
            await self._mock_tick_queues[ticker_key].put(serialized)
            return 1

    async def pop_tick(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Pops the oldest tick from the ticker-specific queue.
        """
        ticker_key = ticker.strip().upper()
        serialized: Optional[str] = None

        if self.mock_mode or not self.redis:
            queue = self._mock_tick_queues.get(ticker_key)
            if not queue:
                return None
            try:
                serialized = queue.get_nowait()
                queue.task_done()
            except asyncio.QueueEmpty:
                return None
        else:
            try:
                serialized = await self.redis.lpop(f"asim:queue:ticks:{ticker_key}")
            except Exception as e:
                logger.error(f"Redis tick pop failed for {ticker_key}: {e}. Checking mock queue.")
                queue = self._mock_tick_queues.get(ticker_key)
                if queue:
                    try:
                        serialized = queue.get_nowait()
                        queue.task_done()
                    except asyncio.QueueEmpty:
                        return None

        if not serialized:
            return None

        try:
            return json.loads(serialized)
        except Exception as e:
            logger.error(f"Failed to deserialize tick item: {e}")
            return None

    async def clear_queues(self) -> bool:
        """
        Clears all buffer queues in both Redis and mock memory.
        """
        # Clear mock structures
        self._mock_news_queue = asyncio.Queue()
        self._mock_tick_queues.clear()

        if self.mock_mode or not self.redis:
            return True

        try:
            # Scan keys matching asim:* and delete
            keys = await self.redis.keys("asim:queue:*")
            if keys:
                await self.redis.delete(*keys)
            logger.info("Cleared all Redis buffer queues.")
            return True
        except Exception as e:
            logger.error(f"Failed to clear Redis queues: {e}")
            return False

    async def close(self) -> None:
        """
        Safely disconnects from the Redis connection pool.
        """
        if self.redis:
            await self.redis.aclose()
        if self.pool:
            await self.pool.disconnect()
        logger.info("Closed Redis connection pool.")
