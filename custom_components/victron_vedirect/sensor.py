from collections.abc import Callable
from enum import Enum, StrEnum
from logging import Logger
import logging
from typing import Type, cast

from attr import dataclass
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.victron_vedirect.domain import VictronVEDirectConfigEntry
from custom_components.victron_vedirect.const import CONF_DEVICE_TYPE, VEDirectKeys, VictronDeviceType
from custom_components.victron_vedirect.coordinator import VictronVEDirectCoordinator
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)

class OffOnOption(StrEnum):
    OFF = 'OFF'
    ON = 'ON'

class OffReasonOptions(StrEnum):
    NO_INPUT_POWER = "1"
    POWER_OFF_SWITCH = "2"
    POWER_OFF_REGISTER = "4"
    REMOTE_INPUT = "8"
    PROTECTION_ACTIVE = "10"
    PAY_AS_YOU_GO_OUT_OF_CREDIT = "20"
    BMS = "40"
    ENGINE_SHUTDOWN = "80"
    ANALYSING_INPUT_VOLTAGE = "100"

class StateOptions(StrEnum):
    OFF = "0"
    LOW_POWER = "1"
    FAULT = "2"
    BULK = "3"
    ABSORPTION = "4"
    FLOAT = "5"
    STORAGE = "6"
    EQUALIZE_MANUAL = "7"
    INVERTING = "9"
    POWER_SUPPLY = "11"
    STARTING_UP = "245"
    REPEATED_ABSORPTION = "246"
    AUTO_EQUALIZE_RECONDITION = "247"
    BATTERY_SAFE = "248"
    EXTERNAL_CONTROL = "252"

class ErrorOptions(StrEnum):
    NO_ERROR = "0"
    BATTERY_VOLTAGE_TOO_HIGH = "2"
    CHARGER_TEMPERATURE_TOO_HIGH = "17"
    CHARGER_OVER_CURRENT = "18"
    CHARGER_CURRENT_REVERSED = "19"
    BULK_TIME_LIMIT_EXCEEDED = "20"
    CURRENT_SENSOR_ISSUE = "21"
    TERMINALS_OVERHEATED = "26"
    CONVERTER_ISSUE = "28"
    INPUT_VOLTAGE_TOO_HIGH = "33"
    INPUT_CURRENT_TOO_HIGH = "34"
    INPUT_SHUTDOWN_BATTERY_VOLTAGE = "38"
    INPUT_SHUTDOWN_CURRENT_FLOW_OFF_MODE = "39"
    LOST_COMMUNICATION_WITH_DEVICE = "65"
    SYNCHRONISED_CHARGING_CONFIGURATION_ISSUE = "66"
    BMS_CONNECTION_LOST = "67"
    NETWORK_MISCONFIGURED = "68"
    FACTORY_CALIBRATION_DATA_LOST = "116"
    INVALID_INCOMPATIBLE_FIRMWARE = "117"
    USER_SETTINGS_INVALID = "119"

class MpptOptions(StrEnum):
    OFF = "0"
    VOLTAGE_OR_CURRENT_LIMITED = "1"
    MPP_TRACKER_ACTIVE = "2"

def enum_value_fn(enum: Type[Enum]):
    """Creates a value function to map an enums value to the name of the enum."""
    def converter(value: str):
        try:
            return enum[value].name
        except KeyError:
            _LOGGER.warning(f"Recieved invalid value for enum {enum.__name__}: '{value}. Falling back to raw value'")
            return value
    return converter

class VictronVEDirectSensorEntityDescription(SensorEntityDescription, frozen_or_thawed=True):
    """Describes a Victron VE.Direct sensor entity."""

    device_types: set[VictronDeviceType]
    """Set of device types that include this entity."""

    value_fn: Callable[[str], float | int | str | None] = lambda x: x
    """Function used to convert the VE.Direct string data into the matching type for the sensor entity."""


BMV_DEVICES = {VictronDeviceType.BMV_60X, VictronDeviceType.BMV_70X, VictronDeviceType.BMV_71X_SMARTSHUNT}


VEDIRECT_SENSOR_DESCRIPTIONS: dict[VEDirectKeys, VictronVEDirectSensorEntityDescription] = {
    # Battery voltages
    ## Main or channel 1 (battery) voltage
    VEDirectKeys.V: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.V,
        value_fn=float,
        translation_key=VEDirectKeys.V,
        device_types={
            VictronDeviceType.BMV_60X,
            VictronDeviceType.BMV_70X,
            VictronDeviceType.BMV_71X_SMARTSHUNT,
            VictronDeviceType.MPPT,
            VictronDeviceType.PHOENIX_CHARGER,
            VictronDeviceType.PHOENIX_INVERTER,
            VictronDeviceType.SMART_BUCKBOOST,
        },
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ## Channel 2 (battery) voltage
    VEDirectKeys.V2: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.V2,
        translation_key=VEDirectKeys.V2,
        device_types={VictronDeviceType.PHOENIX_CHARGER},
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## Channel 3 (battery) voltage
    VEDirectKeys.V3: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.V3,
        translation_key=VEDirectKeys.V3,
        device_types={VictronDeviceType.PHOENIX_CHARGER},
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## Auxiliary (starter) voltage
    VEDirectKeys.VS: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.VS,
        translation_key=VEDirectKeys.VS,
        device_types=BMV_DEVICES,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## Mid-point voltage of the battery bank
    VEDirectKeys.VM: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.VM,
        translation_key=VEDirectKeys.VM,
        device_types={VictronDeviceType.BMV_70X, VictronDeviceType.BMV_71X_SMARTSHUNT},
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## Mid-point deviation of the battery bank
    VEDirectKeys.DM: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.DM,
        translation_key=VEDirectKeys.DM,
        device_types={VictronDeviceType.BMV_70X, VictronDeviceType.BMV_71X_SMARTSHUNT},
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    # PV
    ## Panel voltage
    VEDirectKeys.VPV: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.VPV,
        translation_key=VEDirectKeys.VPV,
        device_types={VictronDeviceType.MPPT},
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## Panel power
    VEDirectKeys.PPV: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.PPV,
        translation_key=VEDirectKeys.PPV,
        device_types={VictronDeviceType.MPPT},
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    # Currents
    ## Main or channel 1 battery current
    VEDirectKeys.I: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.I,
        translation_key=VEDirectKeys.I,
        device_types={
            VictronDeviceType.BMV_60X,
            VictronDeviceType.BMV_70X,
            VictronDeviceType.BMV_71X_SMARTSHUNT,
            VictronDeviceType.MPPT,
            VictronDeviceType.PHOENIX_CHARGER,
            VictronDeviceType.SMART_BUCKBOOST,
        },
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## Channel 2 battery current
    VEDirectKeys.I2: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.I2,
        translation_key=VEDirectKeys.I2,
        device_types={VictronDeviceType.PHOENIX_CHARGER},
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## Channel 3 battery current
    VEDirectKeys.I3: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.I3,
        translation_key=VEDirectKeys.I3,
        device_types={VictronDeviceType.PHOENIX_CHARGER},
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## Load current
    VEDirectKeys.IL: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.IL,
        translation_key=VEDirectKeys.IL,
        device_types={VictronDeviceType.MPPT},
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## Load output state (ON/OFF)
    VEDirectKeys.LOAD: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.LOAD,
        device_class=SensorDeviceClass.ENUM,
        options=OffOnOption._member_names_,
        translation_key=VEDirectKeys.LOAD,
        device_types={VictronDeviceType.MPPT},
        value_fn=enum_value_fn(OffOnOption),
    ),
    ## Battery temperature
    VEDirectKeys.T: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.T,
        translation_key=VEDirectKeys.T,
        device_types={VictronDeviceType.BMV_70X, VictronDeviceType.BMV_71X_SMARTSHUNT},
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## Instantaneous power
    VEDirectKeys.P: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.P,
        translation_key=VEDirectKeys.P,
        device_types={VictronDeviceType.BMV_70X, VictronDeviceType.BMV_71X_SMARTSHUNT},
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## Consumed Amp Hours
    VEDirectKeys.CE: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.CE,
        translation_key=VEDirectKeys.CE,
        device_types=BMV_DEVICES,
        native_unit_of_measurement="mAh",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## State-of-charge
    VEDirectKeys.SOC: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.SOC,
        translation_key=VEDirectKeys.SOC,
        device_types=BMV_DEVICES,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: float(v) / 10,
    ),
    ## Time-to-go
    VEDirectKeys.TTG: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.TTG,
        translation_key=VEDirectKeys.TTG,
        device_types=BMV_DEVICES,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=float,
    ),
    ## Alarm condition active
    VEDirectKeys.ALARM: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.ALARM,
        translation_key=VEDirectKeys.ALARM,
        device_types=BMV_DEVICES,
        value_fn=lambda x:x.upper(),
    ),
    ## Relay state
    VEDirectKeys.RELAY: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.RELAY,
        device_class=SensorDeviceClass.ENUM,
        options= OffOnOption._member_names_,
        translation_key=VEDirectKeys.RELAY,
        device_types={
            VictronDeviceType.BMV_60X,
            VictronDeviceType.BMV_70X,
            VictronDeviceType.BMV_71X_SMARTSHUNT,
            VictronDeviceType.MPPT,
            VictronDeviceType.PHOENIX_INVERTER,
            VictronDeviceType.PHOENIX_CHARGER,
        },
        value_fn=enum_value_fn(OffOnOption),
    ),
    ## Alarm reason
    VEDirectKeys.AR: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.AR,
        translation_key=VEDirectKeys.AR,
        device_types={
            VictronDeviceType.BMV_60X,
            VictronDeviceType.BMV_70X,
            VictronDeviceType.BMV_71X_SMARTSHUNT,
            VictronDeviceType.PHOENIX_INVERTER,
        },
        value_fn=str,
    ),
    ## Off reason
    VEDirectKeys.OR: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.OR,
        device_class=SensorDeviceClass.ENUM,
        options=OffReasonOptions._member_names_,
        device_types={VictronDeviceType.MPPT, VictronDeviceType.PHOENIX_INVERTER},
        translation_key=VEDirectKeys.OR,
        value_fn=enum_value_fn(OffReasonOptions),
    ),
    ## Depth of the deepest discharge
    VEDirectKeys.H1: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H1,
        translation_key=VEDirectKeys.H1,
        device_types=BMV_DEVICES,
        native_unit_of_measurement="mAh",
        value_fn=float,
    ),
    ## Depth of the last discharge
    VEDirectKeys.H2: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H2,
        translation_key=VEDirectKeys.H2,
        device_types=BMV_DEVICES,
        native_unit_of_measurement="mAh",
        value_fn=float,
    ),
    ## Depth of the average discharge
    VEDirectKeys.H3: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H3,
        translation_key=VEDirectKeys.H3,
        device_types=BMV_DEVICES,
        native_unit_of_measurement="mAh",
        value_fn=float,
    ),
    ## Number of charge cycles
    VEDirectKeys.H4: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H4, device_types=BMV_DEVICES, translation_key=VEDirectKeys.H4, value_fn=int
    ),
    ## Number of full discharges
    VEDirectKeys.H5: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H5, device_types=BMV_DEVICES, translation_key=VEDirectKeys.H5, value_fn=int
    ),
    ## Cumulative Amp Hours drawn
    VEDirectKeys.H6: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H6,
        device_types=BMV_DEVICES,
        translation_key=VEDirectKeys.H6,
        native_unit_of_measurement="mAh",
        value_fn=float,
    ),
    ## Minimum main (battery) voltage
    VEDirectKeys.H7: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H7,
        device_types=BMV_DEVICES,
        translation_key=VEDirectKeys.H7,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        value_fn=float,
    ),
    ## Maximum main (battery) voltage
    VEDirectKeys.H8: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H8,
        device_types=BMV_DEVICES,
        translation_key=VEDirectKeys.H8,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        value_fn=float,
    ),
    ## Number of seconds since last full charge
    VEDirectKeys.H9: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H9,
        device_types=BMV_DEVICES,
        translation_key=VEDirectKeys.H9,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=int,
    ),
    ## Number of automatic synchronizations
    VEDirectKeys.H10: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H10, device_types=BMV_DEVICES, translation_key=VEDirectKeys.H10, value_fn=int
    ),
    ## Number of low main voltage alarms
    VEDirectKeys.H11: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H11, device_types=BMV_DEVICES, translation_key=VEDirectKeys.H11, value_fn=int
    ),
    ## Number of high main voltage alarms
    VEDirectKeys.H12: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H12, device_types=BMV_DEVICES, translation_key=VEDirectKeys.H12, value_fn=int
    ),
    ## Number of low auxiliary voltage alarms
    VEDirectKeys.H13: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H13, device_types={VictronDeviceType.BMV_60X}, translation_key=VEDirectKeys.H13, value_fn=int
    ),
    ## Number of high auxiliary voltage alarms
    VEDirectKeys.H14: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H14, device_types={VictronDeviceType.BMV_60X}, translation_key=VEDirectKeys.H14, value_fn=int
    ),
    ## Minimum auxiliary (battery) voltage
    VEDirectKeys.H15: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H15,
        translation_key=VEDirectKeys.H15,
        device_types=BMV_DEVICES,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        value_fn=float,
    ),
    ## Maximum auxiliary (battery) voltage
    VEDirectKeys.H16: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H16,
        translation_key=VEDirectKeys.H16,
        device_types=BMV_DEVICES,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        value_fn=float,
    ),
    ## Amount of discharged energy (BMV) / Amount of produced energy (DC monitor)
    VEDirectKeys.H17: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H17,
        translation_key=VEDirectKeys.H17,
        device_types={VictronDeviceType.BMV_70X, VictronDeviceType.BMV_71X_SMARTSHUNT},
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda v: float(v) / 100,
    ),
    ## Amount of charged energy (BMV) / Amount of consumed energy (DC monitor)
    VEDirectKeys.H18: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H18,
        translation_key=VEDirectKeys.H18,
        device_types={VictronDeviceType.BMV_70X, VictronDeviceType.BMV_71X_SMARTSHUNT},
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda v: float(v) / 100,
    ),
    ## Yield total (user resettable counter)
    VEDirectKeys.H19: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H19,
        translation_key=VEDirectKeys.H19,
        device_types={VictronDeviceType.MPPT},
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda v: float(v) / 100,
    ),
    ## Yield today
    VEDirectKeys.H20: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H20,
        translation_key=VEDirectKeys.H20,
        device_types={VictronDeviceType.MPPT},
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda v: float(v) / 100,
    ),
    ## Maximum power today
    VEDirectKeys.H21: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H21,
        translation_key=VEDirectKeys.H21,
        device_types={VictronDeviceType.MPPT},
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=float,
    ),
    ## Yield yesterday
    VEDirectKeys.H22: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H22,
        translation_key=VEDirectKeys.H22,
        device_types={VictronDeviceType.MPPT},
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda v: float(v) / 100,
    ),
    ## Maximum power yesterday
    VEDirectKeys.H23: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.H23,
        translation_key=VEDirectKeys.H23,
        device_types={VictronDeviceType.MPPT},
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=float,
    ),
    ## Error code
    VEDirectKeys.ERR: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.ERR,
        device_class=SensorDeviceClass.ENUM,
        options=ErrorOptions._member_names_,
        translation_key=VEDirectKeys.ERR,
        device_types={VictronDeviceType.MPPT, VictronDeviceType.PHOENIX_CHARGER, VictronDeviceType.SMART_BUCKBOOST},
        value_fn=enum_value_fn(ErrorOptions),
    ),
    ## State of operation
    VEDirectKeys.CS: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.CS,
        device_class=SensorDeviceClass.ENUM,
        options=StateOptions._member_names_,
        translation_key=VEDirectKeys.CS,
        device_types={
            VictronDeviceType.MPPT,
            VictronDeviceType.PHOENIX_INVERTER,
            VictronDeviceType.PHOENIX_CHARGER,
            VictronDeviceType.SMART_BUCKBOOST,
        },
        value_fn=enum_value_fn(StateOptions),
    ),
    ## Firmware version (16 bit)
    VEDirectKeys.FW: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.FW,
        translation_key=VEDirectKeys.FW,
        device_types={*BMV_DEVICES, VictronDeviceType.MPPT, VictronDeviceType.PHOENIX_INVERTER},
        value_fn=str,
    ),
    ## Firmware version (24 bit)
    VEDirectKeys.FWE: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.FWE,
        translation_key=VEDirectKeys.FWE,
        device_types={VictronDeviceType.PHOENIX_CHARGER, VictronDeviceType.SMART_BUCKBOOST},
        value_fn=str,
    ),
    ## Product ID
    VEDirectKeys.PID: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.PID,
        translation_key=VEDirectKeys.PID,
        device_types={
            VictronDeviceType.BMV_70X,
            VictronDeviceType.BMV_71X_SMARTSHUNT,
            VictronDeviceType.MPPT,
            VictronDeviceType.PHOENIX_INVERTER,
            VictronDeviceType.PHOENIX_CHARGER,
            VictronDeviceType.SMART_BUCKBOOST,
        },
        value_fn=str,
    ),
    ## Serial number
    VEDirectKeys.SERIAL: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.SERIAL,
        translation_key=VEDirectKeys.SERIAL,
        device_types={
            VictronDeviceType.BMV_70X,
            VictronDeviceType.BMV_71X_SMARTSHUNT,
            VictronDeviceType.MPPT,
            VictronDeviceType.PHOENIX_INVERTER,
            VictronDeviceType.PHOENIX_CHARGER,
            VictronDeviceType.SMART_BUCKBOOST,
        },
        value_fn=str,
    ),
    ## Day sequence number
    VEDirectKeys.HSDS: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.HSDS, translation_key=VEDirectKeys.HSDS, device_types={VictronDeviceType.MPPT}, value_fn=int
    ),
    ## Device mode
    VEDirectKeys.MODE: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.MODE,
        translation_key=VEDirectKeys.MODE,
        device_types={
            VictronDeviceType.PHOENIX_INVERTER,
            VictronDeviceType.PHOENIX_CHARGER,
            VictronDeviceType.SMART_BUCKBOOST,
        },
        value_fn=str,
    ),
    ## AC output voltage
    VEDirectKeys.AC_OUT_V: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.AC_OUT_V,
        translation_key=VEDirectKeys.AC_OUT_V,
        device_types={VictronDeviceType.PHOENIX_INVERTER},
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda v: float(v) / 100,
    ),
    ## AC output current
    VEDirectKeys.AC_OUT_I: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.AC_OUT_I,
        translation_key=VEDirectKeys.AC_OUT_I,
        device_types={VictronDeviceType.PHOENIX_INVERTER},
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda v: float(v) / 10,
    ),
    ## AC output apparent power
    VEDirectKeys.AC_OUT_S: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.AC_OUT_S,
        translation_key=VEDirectKeys.AC_OUT_S,
        device_types={VictronDeviceType.PHOENIX_INVERTER},
        native_unit_of_measurement="VA",
        value_fn=float,
    ),
    ## Warning reason
    VEDirectKeys.WARN: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.WARN,
        translation_key=VEDirectKeys.WARN,
        device_types={VictronDeviceType.PHOENIX_INVERTER},
        value_fn=str,
    ),
    ## Tracker operation mode
    VEDirectKeys.MPPT: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.MPPT,
        translation_key=VEDirectKeys.MPPT,
        device_class=SensorDeviceClass.ENUM,
        options=MpptOptions._member_names_,
        device_types={VictronDeviceType.MPPT},
        value_fn=enum_value_fn(MpptOptions),
    ),
    ## DC monitor mode
    VEDirectKeys.MON: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.MON,
        translation_key=VEDirectKeys.MON,
        device_types={VictronDeviceType.BMV_71X_SMARTSHUNT},
        value_fn=str,
    ),
    ## DC input voltage
    VEDirectKeys.DC_IN_V: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.DC_IN_V,
        translation_key=VEDirectKeys.DC_IN_V,
        device_types={VictronDeviceType.SMART_BUCKBOOST},
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda v: float(v) / 100,
    ),
    ## DC input current
    VEDirectKeys.DC_IN_I: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.DC_IN_I,
        translation_key=VEDirectKeys.DC_IN_I,
        device_types={VictronDeviceType.SMART_BUCKBOOST},
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda v: float(v) / 10,
    ),
    ## DC input power
    VEDirectKeys.DC_IN_P: VictronVEDirectSensorEntityDescription(
        key=VEDirectKeys.DC_IN_P,
        translation_key=VEDirectKeys.DC_IN_P,
        device_types={VictronDeviceType.SMART_BUCKBOOST},
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=float,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronVEDirectConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the sensors."""

    coordinator = cast(VictronVEDirectCoordinator,config_entry.runtime_data["coordinator"])
    device_info = config_entry.runtime_data["deviceInfo"]
    device_type = config_entry.data[CONF_DEVICE_TYPE]

    entities = [
        VictronVEDirectSensorEntity(coordinator, config_entry.entry_id, device_info, key, entity_description)
        for key, entity_description in VEDIRECT_SENSOR_DESCRIPTIONS.items()
        if device_type in entity_description.device_types
    ]

    async_add_entities(entities)


class VictronVEDirectSensorEntity(CoordinatorEntity[VictronVEDirectCoordinator], SensorEntity):
    def __init__(
        self, coordinator: VictronVEDirectCoordinator, config_id: str, device_info: DeviceInfo, vedirect_key: VEDirectKeys, entity_description: VictronVEDirectSensorEntityDescription
    ):
        super().__init__(coordinator)

        self._attr_unique_id = f"{config_id}_{vedirect_key}"
        self._attr_device_info = device_info

        self._attr_has_entity_name=True
        self.entity_description: VictronVEDirectSensorEntityDescription = entity_description


        self._attr_available = True
        self._attr_native_value = None

        self.should_poll = False

        self.vedirect_key = vedirect_key

    @callback
    def _handle_coordinator_update(self):
        value = self.coordinator.get_value_by_key(self.vedirect_key)
        parsed_value = value if value is None else self.entity_description.value_fn(value)

        is_update = parsed_value != self._attr_native_value

        if parsed_value is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_native_value = parsed_value

        if is_update:
            self.async_write_ha_state()
