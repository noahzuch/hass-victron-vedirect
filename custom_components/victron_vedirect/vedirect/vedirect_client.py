import asyncio
from enum import Enum
import logging
from typing import Callable

import serial_asyncio_fast

from custom_components.victron_vedirect.vedirect.vedirect_protocol import VEDirectProtocol

_LOGGER = logging.getLogger(__name__)

type StateListener = Callable[[ConnectionState], None]
type TextMessageListener = Callable[[dict[str,str]], None]


class ConnectionState(Enum):
    """The state of the connection of the VEDirectClient."""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"

class VEDirectClient:

    def __init__(self, port: str, baudrate: int = 19200):
        self.port = port
        self.baudrate = baudrate

        self.transport = None
        self.protocol = None

        self.state = ConnectionState.DISCONNECTED
        self._state_listeners : list[StateListener] = []
        self._text_message_listeners: list[TextMessageListener] = []
        self._connect_lock = asyncio.Lock()

        self._last_exception: Exception | None = None

        self._connect_task = None

    # --- Public API ---

    async def async_connect(self):
        if self.state ==  ConnectionState.DISCONNECTED:
            async with self._connect_lock:
                if self.state == ConnectionState.DISCONNECTED:

                    await self._open_connection()

                    self._set_state(ConnectionState.CONNECTED)

    async def async_disconnect(self):
        async with self._connect_lock:
            if self.transport:
                self.transport.close()
                self.transport = None
                self.protocol = None
            if self._connect_task:
                self._connect_task.cancel()
            self._set_state(ConnectionState.DISCONNECTED)

    # --- Internal ---

    async def _open_connection(self):
        loop = asyncio.get_running_loop()

        def factory():
            return VEDirectProtocol(
                on_text_update=self._handle_text_message,
                on_hex_response=lambda x: (),
                on_connection_lost=self._on_connection_lost,
            )

        self.transport, self.protocol = await serial_asyncio_fast.create_serial_connection(
            loop,
            factory,
            self.port,
            baudrate=self.baudrate,
        )

    def _on_connection_lost(self, exc):
        self._last_exception = exc
        self._trigger_connection_loop()

    async def _trigger_connection_loop(self):
        async with self._connect_lock:
            if self.state == ConnectionState.CONNECTED:
                self._set_state(ConnectionState.CONNECTING)
                self.transport = None
                self.protocol = None


            # Start connect loop
            if self._connect_task is None:
                self._connect_task = asyncio.create_task(self._connect_loop())

    async def _connect_loop(self):
        delay = 1

        while True:
            async with self._connect_lock:
                if self.state != ConnectionState.CONNECTING:
                    break # Break out of connecting loop if no longer in state CONNECTING (e.g. async_disconnect() called)

                try:
                    await self._open_connection()
                    self._set_state(ConnectionState.CONNECTED)
                    self._connect_task = None
                    break # Break out of connecting loop if connection was successfull
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    _LOGGER.exception('Error during connection loop. Retrying in %i seconds...', delay)
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 60)  # exponential backoff

    def _set_state(self, new_state):
        self.state = new_state
        for listener in self._state_listeners:
            listener(new_state)

    def async_add_state_listener(self, listener: StateListener) -> None:
        self._state_listeners.append(listener)

    def async_remove_state_listener(self, listener: StateListener) -> None:
        self._state_listeners.remove(listener)

    def async_add_text_message_listener(self, listener: TextMessageListener) -> None:
        self._text_message_listeners.append(listener)

    def async_remove_text_message_listener(self, listener: TextMessageListener) -> None:
        self._text_message_listeners.remove(listener)

    def _handle_text_message(self, msg: dict[str,str]) -> None:
        for listener in self._text_message_listeners:
            listener(msg)

    @property
    def last_exception(self) -> Exception | None:
        return self._last_exception
