from unittest.mock import patch
import pytest
from utils.serial_emulator import SerialEmulator
from utils.virtual_serial_device import VirtualSerialDevice
from utils.async_collector import AsyncCollector
from custom_components.victron_vedirect.vedirect.vedirect_client import ConnectionState


datadict = {'V': '12800', 'VS': '12800', 'VM': '1280', 'DM': '120',
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

def convert():
    result = list()
    for key, value in datadict.items():
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
    return bytes(result)

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

            #When
            await client.async_disconnect()
            assert (await state_collector.get_all(1)) == [ConnectionState.DISCONNECTED]
            assert (await serial_device.close_collector.get_all(1))== [[]]


    @pytest.mark.asyncio
    @pytest.mark.parametrize('chunk_size', generate_chunk_size_options(convert()))
    async def test_my_integration(self, chunk_size):
        emu = SerialEmulator()
        emu.register_device("/dev/victron_mppt", VirtualSerialDevice(convert(), chunk_size=chunk_size))

        # Wir patchen die zentrale Methode von serial_asyncio_fast
        with patch("serial_asyncio_fast.create_serial_connection", side_effect=emu.mock_create_connection):

            from custom_components.victron_vedirect.vedirect.vedirect_client import VEDirectClient
            # Ab hier nutzt deine Integration die Datei, sobald sie
            # create_serial_connection("/dev/victron_mppt", ...) aufruft.
            client = VEDirectClient(port="/dev/victron_mppt")
            text_collector = AsyncCollector()
            client.async_add_text_message_listener(text_collector)
            await client.async_connect()

            assert (await text_collector.get_next()) == {'V': '12800', 'VS': '12800', 'VM': '1280', 'DM': '120',
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
