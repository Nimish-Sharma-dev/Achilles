##! GridSentinel site policy. Logs are written to zeek/logs/ by zeek_sensor.py.

@load ./ics-ot

redef Log::default_logdir = "logs";
redef Site::local_nets += { 10.4.0.0/16 };
