##! ICS/OT notice types — names match zeek_sensor.py / notice.log.

module ICS;

export {
	redef enum Notice::Type += {
		ReplayFlood,
		ModbusExceptionFlood,
		GOOSEStorm,
		FirmwareC2Beacon,
	};
}
