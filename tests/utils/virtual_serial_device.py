import asyncio
from unittest import mock
from utils.async_collector import AsyncCollector

class VirtualSerialDevice:
    def __init__(self, data_source: bytes, chunk_size: int | None = None, manual: bool =False):
        self.data_source = data_source
        self.chunk_size = chunk_size
        self.close_collector = AsyncCollector()
        self.transport = mock.Mock(spec=asyncio.Transport)
        self.transport.close = self.close_collector
        self.protocol = None
        self._trigger = asyncio.Event()
        self._manual_mode = manual

    def inject_into_protocol(self, protocol):
        """
        Connects the protocol and starts the data delivery loop.
        Set manual=True to wait for manual 'trigger_next()' calls.
        """
        self.protocol = protocol
        self.protocol.connection_made(self.transport)

        # Start the background delivery task
        asyncio.create_task(self._deliver_data())

    async def _deliver_data(self):
        """Internal loop to feed data to the protocol in chunks."""
        offset = 0
        total = len(self.data_source)

        while offset < total:
            # 1. Wait for trigger if in manual mode
            if self._manual_mode:
                await self._trigger.wait()
                self._trigger.clear()

            # 2. Determine chunk size
            size = self.chunk_size or total
            chunk = self.data_source[offset : offset + size]

            # 3. Deliver to protocol
            if self.protocol:
                self.protocol.data_received(chunk)

            offset += len(chunk)

            # Small yield to let the loop process the data_received call
            await asyncio.sleep(0)

    def trigger_next(self):
        """Manually trigger the delivery of the next chunk."""
        self._trigger.set()

    async def simulate_write_response(self, response: bytes):
        """
        """
        pass
