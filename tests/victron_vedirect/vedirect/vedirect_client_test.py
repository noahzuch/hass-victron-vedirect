from unittest.mock import patch
import pytest
from utils.serial_emulator import SerialEmulator
from utils.virtual_serial_device import VirtualSerialDevice
from utils.async_collector import AsyncCollector
from custom_components.victron_vedirect.vedirect.vedirect_client import ConnectionState


example_block = {'V': '12800', 'VS': '12800', 'VM': '1280', 'DM': '120',
                     'VPV': '3350', 'PPV': '130', 'I': '15000', 'IL': '1500',
                     'LOAD': 'ON', 'T': '25', 'P': '130', 'CE': '13500',
                     'SOC': '876', 'TTG': '45', 'Alarm': 'OFF', 'Relay': 'OFF',
                     'AR': '1', 'H1': '55000', 'H2': '15000', 'H3': '13000',
                     'H4': '230', 'H5': '12', 'H6': '234000', 'H7': '11000',
                     'H8': '14800', 'H9': '7200', 'H10': '45', 'H11': '5',
                     'H12': '0', 'H13': '0', 'H14': '0', 'H15': '11500',
                     'H16': '14800', 'H17': '34', 'H18': '45', 'H19': '456',
                     'H20': '45', 'H21': '300', 'H22': '45', 'H23': '350',
                     'ERR': '0', 'CS': '5', 'BMV': '702', 'FW': '1.19',
                 'PID': '0x204', 'SER#': 'HQ141112345', 'HSDS': '0'}

def convert_blocks_to_bytes(blocks: list[dict[str,str]]):

    total_result = list()

    for block in blocks:
        result = list()
        for key, value in block.items():
            result.append(ord('\r'))
            result.append(ord('\n'))
            result.extend([ord(i) for i in key])
            result.append(ord('\t'))
            result.extend([ord(i) for i in value])
        # checksum
        result.append(ord('\r'))
        result.append(ord('\n'))
        result.extend([ord(i) for i in 'Checksum'])
        result.append(ord('\t'))
        result.append((256 - (sum(result) % 256)) % 256)

        total_result.extend(result)
    return bytes(total_result)

def generate_chunk_size_options(data: bytes):
    return range(1,len(data), len(data)//10)


class TestVEDirectProtocol:

    @pytest.mark.asyncio
    async def test_async_connect_successfully_connects(self):
        # Given
        emu = SerialEmulator()
        serial_device = VirtualSerialDevice(bytes())
        emu.register_device("/dev/victron_mppt", serial_device)

        with patch("serial_asyncio_fast.create_serial_connection", side_effect=emu.mock_create_connection):

            from custom_components.victron_vedirect.vedirect.vedirect_client import VEDirectClient
            client = VEDirectClient(port="/dev/victron_mppt")

            state_collector = AsyncCollector()
            client.async_add_state_listener(state_collector)

            # With
            assert client.state == ConnectionState.DISCONNECTED

            # When
            await client.async_connect()

            # Then
            assert (await state_collector.get_next()) == ConnectionState.CONNECTED


    @pytest.mark.asyncio
    async def test_async_disconnect_successfully_disconnects(self):
        # Given
        emu = SerialEmulator()
        serial_device = VirtualSerialDevice(bytes())
        emu.register_device("/dev/victron_mppt", serial_device)

        with patch("serial_asyncio_fast.create_serial_connection", side_effect=emu.mock_create_connection):

            from custom_components.victron_vedirect.vedirect.vedirect_client import VEDirectClient
            client = VEDirectClient(port="/dev/victron_mppt")

            state_collector = AsyncCollector()
            client.async_add_state_listener(state_collector)
            await client.async_connect()
            # Assume
            assert (await state_collector.get_all(1)) == [ConnectionState.CONNECTED]

            # When
            await client.async_disconnect()

            # Then
            assert (await state_collector.get_all(1)) == [ConnectionState.DISCONNECTED]
            assert (await serial_device.close_collector.get_all(1))== [()]


    @pytest.mark.asyncio
    # Use different chunk sizes to test state machine
    @pytest.mark.parametrize('chunk_size', generate_chunk_size_options(convert_blocks_to_bytes([example_block])))
    async def test_text_message_listener_called__for_single_valid_message(self, chunk_size: int):
        emu = SerialEmulator()
        emu.register_device("/dev/victron_mppt", VirtualSerialDevice(convert_blocks_to_bytes([example_block]), chunk_size=chunk_size))

        with patch("serial_asyncio_fast.create_serial_connection", side_effect=emu.mock_create_connection):

            from custom_components.victron_vedirect.vedirect.vedirect_client import VEDirectClient
            client = VEDirectClient(port="/dev/victron_mppt")

            text_collector = AsyncCollector()
            client.async_add_text_message_listener(text_collector)
            await client.async_connect()

            assert (await text_collector.get_next()) == example_block


    @pytest.mark.asyncio
    async def test_text_message_listener_called__for_multiple_valid_messages(self):
        emu = SerialEmulator()
        emu.register_device("/dev/victron_mppt", VirtualSerialDevice(convert_blocks_to_bytes([example_block, example_block, example_block]), chunk_size=10))

        with patch("serial_asyncio_fast.create_serial_connection", side_effect=emu.mock_create_connection):

            from custom_components.victron_vedirect.vedirect.vedirect_client import VEDirectClient
            client = VEDirectClient(port="/dev/victron_mppt")

            text_collector = AsyncCollector()
            client.async_add_text_message_listener(text_collector)
            await client.async_connect()

            assert (await text_collector.get_all(3)) == [example_block, example_block, example_block]

    @pytest.mark.asyncio
    async def test_text_message_listener__can_handle_partial_message(self):
        """This test validates that the client can recover from partial blocks where some suffix of the block was sent, before the client connected.

        The basic idea is that we send a partial block starting at every possible offset from 1 to length of one block.
        After this partial block, a valid block is sent. The client has to recover from reading the first partial block
        and be able to parse the second valid block."""

        single_block_length = len(convert_blocks_to_bytes([example_block]))
        input_bytes = convert_blocks_to_bytes([example_block, example_block])

        # Some offsets generate a partial block that is still valid, as the checksum by chance matches. These have to be
        # ignored
        excluded_offsets = {360}
        for offset in range(1,single_block_length):
            if offset in excluded_offsets:
                continue
            # print(f"Offset: {offset}. Starting with {str(input_bytes[offset:offset+15])}")
            emu = SerialEmulator()
            emu.register_device("/dev/victron_mppt", VirtualSerialDevice(input_bytes[offset:]))

            with patch("serial_asyncio_fast.create_serial_connection", side_effect=emu.mock_create_connection):

                from custom_components.victron_vedirect.vedirect.vedirect_client import VEDirectClient
                client = VEDirectClient(port="/dev/victron_mppt")

                text_collector = AsyncCollector()
                client.async_add_text_message_listener(text_collector)
                await client.async_connect()

                assert (await text_collector.get_next()) == example_block
