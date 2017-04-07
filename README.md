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

	from sphero_sprk import Sphero	
	
	orb = Sphero("C8:A2:4D:7D:FA:4F")
	orb.connect()
	orb.set_rgb_led(255,0,0)


Currently supported commands
----------------------------------
 
 General
 - ping()
 - version()
 - get_device_name()


 Sphero
 - set_rgb_led(red, green, blue)
 - get_rgb_led()
 - start_gyro_callback(callback function)
 - start_accel_callback(callback function)
 - start_imu_callback(callback function)
 - set_stabilization(bool)
 - set_raw_motor_values(lmode, lpower, rmode, rpower)
 - set_heading(new_zero_heading_according_to_old_heading)
 - roll(heading, speed)


 Common Errors
 ---------------------------------------
 
*  if program throws `FileNotFoundError: [Errno 2] No such file or directory: '/home/$USER/python3.4/site-packages/bluepy/bluepy-helper'.` Go to the directory where bluepy is installed(`/home/$USER/python3.4/site-packages/bluepy/`) and run the makefile located in the directory.
*  if the program halts at the beginning, restarting the program a few times will solve the problem. There's a known issue with bluepy sometimes getting stuck at the initialization phase.

Contact & License
----------------------------------------------
Created and Maintained by CMU Assistive Robots Lab
Contact:  Zhi <zhi.tan@ri.cmu.edu>

Licensed under the MIT license
