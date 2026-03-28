import asyncio
from enum import Enum
import logging
from typing import Callable, override

from custom_components.victron_vedirect.vedirect.text_mode_interface import VEDIRECT_TEXT_KEYS

_LOGGER = logging.getLogger(__name__)


BAUD_RATE = 19200

TEXT_HEADER1 = ord(b"\r")
TEXT_HEADER2 = ord(b"\n")
TEXT_DELIMETER = ord(b"\t")

HEX_HEADER = ord(b":")
HEX_FOOTER = ord(b"\n")


class RecieveState(Enum):
    WAIT_HEADER = 0
    PARSE_KEY = 1
    PARSE_VALUE = 2
    PARSE_CHECKSUM = 3
    HEX = 4


class VEDirectProtocol(asyncio.Protocol):
    def __init__(self, on_text_update: Callable[[dict[str,str]],None], on_hex_response, on_connection_lost: Callable[[Exception], None]) -> None:
        self.text_buffer = bytearray()
        self.text_byte_sum = 0
        self.current_field_key: str | None = None
        self.block = {}
        self.on_text_update = on_text_update
        self.on_hex_response = on_hex_response
        self._on_connection_lost = on_connection_lost

        self.state: RecieveState = RecieveState.WAIT_HEADER

    @override
    def data_received(self, data: bytes) -> None:
        for byte in data:
            if byte == HEX_HEADER and self.state != RecieveState.PARSE_CHECKSUM:
                self.state = RecieveState.HEX

            match self.state:
                case RecieveState.WAIT_HEADER:
                    self.text_buffer.clear()
                    self.current_field_key = None

                    self.text_byte_sum += byte
                    if byte == TEXT_HEADER1:
                        self.state = RecieveState.WAIT_HEADER
                    elif byte == TEXT_HEADER2:
                        self.state = RecieveState.PARSE_KEY
                    elif byte == HEX_HEADER:
                        self.state = RecieveState.HEX

                case RecieveState.PARSE_KEY:
                    self.text_byte_sum += byte
                    if byte == TEXT_DELIMETER:
                        self.current_field_key = self.text_buffer.decode("ascii")
                        self.text_buffer.clear()

                        if self.current_field_key == "Checksum":
                            self.state = RecieveState.PARSE_CHECKSUM
                        else:
                            self.state = RecieveState.PARSE_VALUE
                    else:
                        # TODO add timeout
                        self.text_buffer.append(byte)

                case RecieveState.PARSE_VALUE:
                    self.text_byte_sum += byte
                    if byte == TEXT_HEADER1:
                        self.state = RecieveState.WAIT_HEADER
                        if self.current_field_key:
                            self._add_field_to_block(self.current_field_key, self.text_buffer.decode("ascii"))
                        self.text_buffer.clear()
                    else:
                        # TODO add timeout
                        self.text_buffer.append(byte)

                case RecieveState.PARSE_CHECKSUM:
                    self.text_byte_sum += byte
                    self.state = RecieveState.WAIT_HEADER
                    if self.text_byte_sum % 256 == 0:
                        self.on_text_update(self.block)

                    self.text_byte_sum = 0
                    self.block = {}
                case RecieveState.HEX:
                    # TODO implement
                    if byte == HEX_FOOTER:
                        self.state = RecieveState.WAIT_HEADER

    def _add_field_to_block(self, field_key: str, value: str) -> None:
        if field_key not in VEDIRECT_TEXT_KEYS:
            _LOGGER.warning(f"Unknown field parsed: {field_key}. Field gets ignored...")
            return

        self.block[field_key] = value


    @override
    def connection_lost(self, exc: Exception | None) -> None:
        self._on_connection_lost(exc)
