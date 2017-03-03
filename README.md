Sphero_SPRK
============
An python module that connects with Sphero SPRK+. Under development

Requirements:
--------------------
- Linux (bluepy & bluez dependence)
- \>= python3.3 

Installation
--------------------
To install the latest released version:

	$ pip install sphero_sprk
	$ cd <python site package>/bluepy
	$ make

Usage Example
---------------------------

	orb = Sphero("C8:A2:4D:7D:FA:4F")
	orb.connect()
	orb.set_rgb_led(255,0,0)


Currently supported commands
----------------------------------
 - set_rgb_led(red, green, blue)
 - get_rgb_led()
 - start_gyro_callback(callback function)
 - start_accel_callback(callback function)
 - start_imu_callback(callback function)
 - set_stabilization(bool)
 - set_raw_motor_values(lmode, lpower, rmode, rpower)
