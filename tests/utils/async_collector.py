import asyncio
import pytest

class AsyncCollector:
    def __init__(self, timeout=1.0):
        self.queue = asyncio.Queue()
        self.timeout = timeout
        self.loop = asyncio.get_running_loop()

    def __call__(self, *args):
        # Package the arguments
        result = args[0] if len(args) == 1 else args
        # Thread-safe put into the queue
        self.loop.call_soon_threadsafe(self.queue.put_nowait, result)

    async def get_next(self):
        """Wait for the next individual call."""
        return await asyncio.wait_for(self.queue.get(), timeout=self.timeout)

    async def get_all(self, count):
        """Wait until 'count' messages have been received. Checks, that exactly the specified number of invocations happend"""
        results = []
        for _ in range(count):
            results.append(await self.get_next())
        try:
            await self.get_next()
            raise ValueError(f"Expected {count} invocations, but got more.")
        except TimeoutError:
            return results
