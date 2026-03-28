from unittest.mock import patch
from utils.virtual_serial_device import VirtualSerialDevice

class SerialEmulator:
    def __init__(self):
        self.registry: dict[str,VirtualSerialDevice] = {}

    def register_device(self, port: str, device: VirtualSerialDevice):
        self.registry[port] = device

    async def mock_create_connection(self, loop, protocol_factory, port, *args, **kwargs):
        protocol = protocol_factory()
        device = self.registry[port]
        device.inject_into_protocol(protocol)

        return device.transport, protocol

