#!/usr/bin/python3

import sys
import time
import binascii
import os
import threading

import bluepy
import yaml
from .util import *

#should it be in a different format?
RobotControlService = "22bb746f2ba075542d6f726568705327"
BLEService = "22bb746f2bb075542d6f726568705327"
AntiDosCharacteristic = "22bb746f2bbd75542d6f726568705327"
TXPowerCharacteristic = "22bb746f2bb275542d6f726568705327"
WakeCharacteristic = "22bb746f2bbf75542d6f726568705327"
ResponseCharacteristic = "22bb746f2ba675542d6f726568705327"
CommandsCharacteristic = "22bb746f2ba175542d6f726568705327"

# class DATA_MASK_LIST(object):
#     IMU_PITCH = bytes.fromhex("0004 0000")
#     IMU_ROLL = bytes.fromhex("0002 0000")
#     IMU_YAW = bytes.fromhex("0001 0000")
#     ACCEL_X = bytes.fromhex("0000 8000")
#     ACCEL_Y = bytes.fromhex("0000 4000")
#     ACCEL_Z = bytes.fromhex("0000 2000")
#     GYRO_X = bytes.fromhex("0000 1000")
#     GYRO_Y = bytes.fromhex("0000 0800")
#     GYRO_Z = bytes.fromhex("0000 0400")


class DelegateObj(bluepy.btle.DefaultDelegate):
    """
    Delegate object that get calls when there is a notification
    """
    def __init__(self, sphero_obj,lock):
        bluepy.btle.DefaultDelegate.__init__(self)
        self._sphero_obj = sphero_obj
        self._callback_dict = {}
        self._wait_list = {}
        self._data_group_callback = {}
        self._enabled_group = []
        self._buffer_bytes = b''
        self._notification_lock = lock

    def register_callback(self, seq, callback):
        self._callback_dict[seq] = callbackl

    def register_async_callback(self, group_name, callback):
        self._data_group_callback[group_name] = callback
        self._enabled_group = list(set(self._enabled_group) | set([group_name]))

    def handle_callbacks(self, packet):
        #unregister callback
        callback = self._callback_dict.pop(packet[3])
        MRSP = packet[2]
        dlen = (packet[4] - 1)
        data = []
        if(dlen > 0):
            data = packet[5:5+dlen]
        #parse the packet
        callback(MRSP, data)

    def wait_for_resp(self,seq,timeout=None):
        #this is a dangerous function, it waits for a response in the handle notification part
        self._wait_list[seq] = None;
        while(self._wait_list[seq] == None):
            #time.sleep(0.1)
            with self._notification_lock:
                self._sphero_obj._device.waitForNotifications(0.05)
        return self._wait_list.pop(seq)

    def wait_for_sim_response(self, seq, timeout=None):
        #this is a dangerous function, it waits for a response in the handle notification part
        self._wait_list[seq] = None;
        while(self._wait_list[seq] == None):
            #time.sleep(0.1)
            with self._notification_lock:
                self._sphero_obj._device.waitForNotifications(0.05)
        data = self._wait_list.pop(seq)
        return (len(data) == 6 and data[0] == 255)    

    def parse_single_pack(self, data):

        if(data[1] == 255):
            #get the sequence number and check if a callback is assigned
            if(data[3] in self._callback_dict):
                self.handle_callbacks(data)
            #check if we have it in the wait list
            elif(data[3] in self._wait_list):
                self._wait_list[data[3]] = data
            #simple response
            elif(len(data) == 6 and data[0] == 255 and data[2] == 0):
                pass
                #print("receive simple response for seq:{}".format(data[3]))
            else:
                print("unknown response:{}".format(data))
            #Sync Message
        elif(data[1] == 254):
            ##print("receive async")
            #Async Message
            if(data[2] == int.from_bytes(b'\x03','big')):
                #the message is sensor data streaming
                #get the number of bytes
                data_length = int.from_bytes(data[3:5],'big') - 1#minus one for the checksum_val


                index = 5 #where the data starts

                #the order is same as the mask list
                mask_list = self._sphero_obj._mask_list
                for i,info in enumerate(mask_list):
                    group_key = info["name"]
                    #check if we enable the group
                    if(group_key in self._enabled_group):
                        group_info = info["values"]
                        info = {}
                        for i,value in enumerate(group_info):
                            end_index = index + 2
                            #it's a 16bit value
                            info[value["name"]] = int.from_bytes(data[index:end_index],'big',signed=True)
                            index = end_index
                        #now we pass the info to the callback
                        # might think about spliting this into a different thread
                        if group_key in self._data_group_callback:
                            self._data_group_callback[group_key](info)
            elif(data[2] == int.from_bytes(b'\x09','big')):
                #orbbasic error message:
                print("orbBasic Error Message:")
                print(data[2:])
            elif(data[2] == int.from_bytes(b'\x0A','big')):
                print(data[2:])
            else:
                print("unknown async response:{}".format(data))
        else:
            pass

    def handleNotification(self, cHandle, data):

        #merge the data with previous incomplete instance
        self._buffer_bytes =  self._buffer_bytes + data

        #loop through it and see if it's valid
        while(len(self._buffer_bytes) > 0):
                #split the data until it's a valid chunk
                index = 1
                max_size = len(self._buffer_bytes)
                data_single = self._buffer_bytes[:index]
                while (not package_validator(data_single) and index <= max_size):
                    index += 1
                    data_single = self._buffer_bytes[:index]

                if(index >= max_size):
                    #this mean the whole buffer it the message,
                    #it either could mean it's invalid or valid
                    if(package_validator(data_single)):
                        #this mean the data is valid
                        self._buffer_bytes = b'' #clear the buffer
                    else:
                        #this mean the data is not valid
                        #keep the existing data in the buffer
                        break #because we don't have enough data to parse anything
                #resize the new buffer
                self._buffer_bytes = self._buffer_bytes[index:]

                #now we parse a single instant
                self.parse_single_pack(data_single)


class Sphero(object):

    RAW_MOTOR_MODE_OFF = "00"
    RAW_MOTOR_MODE_FORWARD = "01"
    RAW_MOTOR_MODE_REVERSE = "02"
    RAW_MOTOR_MODE_BRAKE = "03"
    RAW_MOTOR_MODE_IGNORE = "04"

    def __init__(self, addr=None):


        if(addr == None):
            #search for sphero
            sphero_list = search_for_sphero()
            if(len(sphero_list) == 0):
                raise "No Sphero Found in Vicinity"
            addr = sphero_list[0]

        self._addr = addr
        self._connected = False
        self._seq_counter = 0
        self._stream_rate = 10
        #load the mask list
        with open(os.path.join(os.path.dirname(__file__),'data','mask_list.yaml'),'r') as mask_file:
            self._mask_list = yaml.load(mask_file)
        self._curr_data_mask = bytes.fromhex("0000 0000")

        self._notification_lock = threading.RLock()
        #start a listener loop

    def connect(self):
        """
        Connects the sphero with the address given in the constructor
        """
        self._device = bluepy.btle.Peripheral(self._addr, addrType=bluepy.btle.ADDR_TYPE_RANDOM)
        self._notifier = DelegateObj(self, self._notification_lock)
        #set notifier to be notified
        self._device.withDelegate(self._notifier)

        self._devModeOn()
        self._connected = True #Might need to change to be a callback format
        #get the command service
        cmd_service = self._device.getServiceByUUID(RobotControlService)
        self._cmd_characteristics = {}
        characteristic_list = cmd_service.getCharacteristics()
        for characteristic in characteristic_list:
            uuid_str = binascii.b2a_hex(characteristic.uuid.binVal).decode('utf-8')
            self._cmd_characteristics[uuid_str] = characteristic

        self._listening_flag = True
        self._listening_thread = threading.Thread(target=self._listening_loop)
        self._listening_thread.start()


    def _devModeOn(self):
        """
        A sequence of read/write that enables the developer mode
        """
        service = self._device.getServiceByUUID(BLEService)
        characteristic_list = service.getCharacteristics()
        #make it into a dict
        characteristic_dict = {}
        for characteristic in characteristic_list:
            uuid_str = binascii.b2a_hex(characteristic.uuid.binVal).decode('utf-8')
            characteristic_dict[uuid_str] = characteristic

        characteristic = characteristic_dict[AntiDosCharacteristic]
        characteristic.write("011i3".encode(),True)
        characteristic = characteristic_dict[TXPowerCharacteristic]
        characteristic.write((7).to_bytes(1, 'big'),True)
        characteristic = characteristic_dict[WakeCharacteristic]
        characteristic.write((1).to_bytes(1, 'big'),True)       

    def command(self, cmd, data, resp=True):
        """
        cmd - (str) Hex String that is the command's code(ff, no need to put \\x in front)
        data - [bytes/str/int] an array of values with what to send. We will reformat int and string
        resp - (bool) whether the command will only return after we get an acknowledgement from Sphero. If set to false, sphero will be set to NOT even send a response to save bandwidth
        -----
        
        return - (tuple) A tuple with the first element being sequence number and second element being the response if blocked, None if not 
        """      
        #format data  
        data_list = self._format_data_array(data)
        #set the sop2 based on the blocking command
        sop2 = "ff" if resp else "fe"
        #send command
        seq_num = self._send_command(sop2, "02", cmd, data_list)
        #check if blocking
        if(resp):
            resp = self._notifier.wait_for_resp(seq_num)
            #return the sequence number and response 
            return (seq_num, resp)
        else:
            return (seq_num, None)

    def _send_command(self,sop2,did,cid,data_list):
        
        sop1 = binascii.a2b_hex("ff")
        sop2 = binascii.a2b_hex(sop2)
        did = binascii.a2b_hex(did)
        cid = binascii.a2b_hex(cid)
        seq_val = self._get_sequence()
        seq = seq_val.to_bytes(1,"big")
        dlen = (count_data_size(data_list)+1).to_bytes(1,"big")#add one for checksum
        packet = [sop1,sop2,did,cid,seq,dlen] + data_list
        packet += [cal_packet_checksum(packet[2:]).to_bytes(1,'big')] #calculate the checksum
        #write the command to Sphero
        #print("cmd:{} packet:{}".format(cid, b"".join(packet)))
        with self._notification_lock:
            self._cmd_characteristics[CommandsCharacteristic].write(b"".join(packet))
        return seq_val        


    # def sleep(self, timeout):
    #     """
    #     Sleep function that allows the notifications to be fired
    #     """
    #     startTime = time.time()
    #     while(time.time() - startTime <= timeout):
    #         #time.sleep(1)
    #         #self._device.waitForNotifications(1)

    def _listening_loop(self):
        pass
        #while(self._listening_flag):
            #with self._notification_lock:
                #self._device.waitForNotifications(0.001)

    def _get_sequence(self):
        val = self._seq_counter
        self._seq_counter += 1
        self._seq_counter = self._seq_counter%256
        return val

    def _format_data_array(self, arr):
        """
        helper function that converts int or string to bytes, just want to decrease the number of codes
        """
        if isinstance(arr,list): 
            for i,value in enumerate(arr):
                if isinstance(value, str):
                    arr[i] = binascii.a2b_hex(value)
                elif isinstance(value, int):
                    arr[i] = value.to_bytes(1,'big')
        return arr

    """ CORE functionality """

    def ping(self):
        return self._send_command("ff","00","01",[])

    def version(self):
        #NOTE returning weird data not sure what's wrong
        seq_num = self._send_command("ff","00","02",[])
        response = self._notifier.wait_for_resp(seq_num)
        data_response = response[5:-1]
        version_data = {}
        version_data["RECV"] = hex(data_response[0])
        version_data["MDL"] = hex(data_response[1])
        version_data["HW"] = data_response[2]
        version_data["MSA-ver"] = data_response[3]
        version_data["MSA-rev"] = data_response[4]
        version_data["BL"] = hex(data_response[5])
        return version_data

    def get_device_name(self):
        seq_num = self._send_command("ff","00","11",[])
        response = self._notifier.wait_for_resp(seq_num)
        name_data = {}
        name_data["name"] = str(response[5:21],'utf-8').rstrip(' \t\r\n\0')
        name_data["bta"] = str(response[21:33],'utf-8')
        name_data["color"] = str(response[33:36],'utf-8')
        return name_data


    """ Sphero functionality """

    def roll(self, speed, heading, resp=False):
        """
        Roll the ball towards the heading

        speed - (int) speed
        heading - (int) which direction, 0 - 359
        resp - (bool) whether the code will wait for comfirmation from Sphero
        """
        heading_bytes = heading.to_bytes(2,byteorder='big')
        data = [speed,heading_bytes[0],heading_bytes[1], 1]
        #send command
        self.command('30',data, resp=resp)


    def boost(self):
        raise NotImplementedError

    def set_heading(self, heading, resp=False):
        """
        change the heading of the robot

        heading - (int) heading in the range of 0-355
        resp - (bool) Whether to receive comfirmation response from sphero
        """
        heading_bytes = heading.to_bytes(2,byteorder='big')
        data = [heading_bytes[0],heading_bytes[1]]
        #send command
        self._command("01",data, resp=resp)


    def set_rgb_led(self, red, green, blue, resp=False):
        """
        Set the color of Sphero's LED

        red - (int) Color of red in range 0-255
        green - (int) Color of green in range 0-255
        blue - (int) Color of blue in range 0-255
        resp - (bool) whether the code will wait for comfirmation from Sphero
        """
        #set data
        data = [red, green, blue, 0]
        #send command
        self.command("20", data, resp=resp)


    def get_rgb_led(self):
        """
        Get the color of Sphero's LED
        ----
        return - tuple of the color in RGB
        """

        #set the correct command
        (seq_num, resp) = self.command("22",[])
        #parse the response packet and make sure it's correct
        if resp and resp[4] == 4:
            MRSP = resp[2]
            red = resp[5]
            green = resp[6]
            blue = resp[7]
            return (red, green, blue)
        else:
            return None

    def _handle_mask(self,group_name, remove=False):

        if(remove):
            optr = XOR_mask
        else:
            optr = OR_mask
        for i,group in enumerate(self._mask_list):
            if(group["name"] == group_name):
                for i, value in enumerate(group["values"]):
                    self._curr_data_mask = optr(self._curr_data_mask, bytes.fromhex(value["mask"]))


    def _start_data_stream(self, group_name,rate):
        ##  '\xff\xff\x02\x11\x01\x0e\x00(\x00\x01\x00\x00\x1c\x00\x00\x00\x00\x00\x00\x98'

        #handle mask
        self._handle_mask(group_name)
        #send the mask as data
        self._stream_rate = rate
        self._send_data_command(rate,self._curr_data_mask,(0).to_bytes(4,'big'))

    def _send_data_command(self,rate,mask1,mask2,sample=1):
        N = ((int)(400/rate)).to_bytes(2,byteorder='big')
        #N = (40).to_bytes(2,byteorder='big')
        M = (sample).to_bytes(2,byteorder='big')
        PCNT = (0).to_bytes(1,'big')
        #MASK2 = (mask2).to_bytes(4,'big')
        data = [N,M, mask1 ,PCNT,mask2]
        self.command("11",data, resp=True) #make sure sphero actully receive this


    def _stop_data_stream(self, group_name):
        #handle mask
        self._handle_mask(group_name,remove=True)
        self._send_data_command(self._stream_rate,self._curr_data_mask,(0).to_bytes(4,'big'))


    def start_gyro_callback(self,rate,callback):
        """
        Set a gyro callback that streams the data to the callback

        callback - (function) function that we will pass the information when there is a callback
        """
        name = "Gyro"
        #first we register the callback with the notifier
        self._notifier.register_async_callback(name,callback)
        #start data stream
        self._start_data_stream(name,rate)

    def start_accel_callback(self,rate,callback):
        """
        Set a accelerator callback that streams the data to the callback

        callback - (function) function that we will pass the information when there is a callback
        """
        name = "Accel"
        #first we register the callback with the notifier
        self._notifier.register_async_callback(name,callback)
        #start data stream
        self._start_data_stream(name,rate)

    def start_IMU_callback(self,rate,callback):
        """
        Set a IMU callback that streams the data to the callback

        callback - (function) function that we will pass the information when there is a callback
        """
        name = "IMU"
        #first we register the callback with the notifier
        self._notifier.register_async_callback(name,callback)
        #start data stream
        self._start_data_stream(name,rate)

    def stop_gyro_callback(self):
        self._stop_data_stream("Gyro")

    def stop_accel_callback(self):
        self._stop_data_stream("Accel")

    def stop_IMU_callback(self):
        self._stop_data_stream("IMU")

    def set_stabilization(self,bool_flag, resp=False):
        """
        Enable/Disable stabilization of Sphero

        bool_flag - (bool) stabilization on/off
        resp[Optional] - (bool) whether the code will wait for comfirmation from Sphero, default to False
        """
        data = ["01" if bool_flag else "00"]
        self.command("02",data, resp=resp)


    def set_raw_motor_values(self,lmode,lpower,rmode,rpower, resp=False):
        """
        Set the raw motor values of Sphero
        lmode - (str) the hex string(without \\x) of the mode
        lpower - (int) the value of the power from 0-255
        rmode - (str) the hex string(without \\x) of the mode
        rpower - (int) the value of the power from 0-255
        resp[Optional] - (bool) whether the code will wait for comfirmation from Sphero, default to False
        """
        data = [lmode, int(lpower), rmode, int(rpower)]
        
        #By default, we going to cancel it
        self.command("33",data, resp=resp) 

    """ About MACRO  """

    def abort_macro(self, id_):
        """
        Abort the current macro with the given ID
        id - (int) the ID of the macro to stop
        """
        data = [id_]
        self.command("55",data)

    def run_macro(self, id_):
        """
        Start the macro with the given ID
        id_ - (int) the 8-bit ID of the macro
        """
        data = [id_]
        self.command("50",data)

    """ OrbBasic the programming language """

    STORAGE_RAM = "00"
    STORAGE_PERSISTENT = "01"

    def erase_orb_basic_storage(self, area, block=True):
        """
        Erase any existing program in the stored area
        area - (str) hex name of the area to be cleaned
        """
        data = [area]
        seq = self.command("60", data)
        if(block):
            return self._notifier.wait_for_sim_response(seq)
        else:
            return True

    def run_orb_basic_program(self, area, start_line):
        """
        Run a the orb_basic program stored in that area
        area - (str) hex name of the area
        start_line - (int) the decimal line number to start
        """
        data = [area,start_line.to_bytes(2,byteorder='big')]

        seq = self.command("62", data)
        return self._notifier.wait_for_sim_response(seq)

    def abort_orb_basic_program(self):
        """
        Abort the orb_basic program
        """
        data = []
        seq = self.command("63", data)
        return self._notifier.wait_for_sim_response(seq)

    def append_orb_basic_fragment(self, area,val):
        """
        Append the value into ht orb basic given the area
        val - (list of strings) the command broken down into a list of hex values
        area - (str) hex name of the area
        """
        val.insert(0, area)
        data = val
        seq = self.command("61",data)
        if self._notifier.wait_for_sim_response(seq):
            pass
        else:
            print("error in appending orbbasic fragments")

    def append_orb_basic_line(self, area,code):
        """
        Append the line to the existing code
        """
        #first convert the line into list of bytes
        code_list = []
        for c in code:
            code_list.append(bytes(c,encoding="UTF-8"))
        if len(code_list) == 0:
            code_list.append(b'\x00') # NULL in the end
        #code_list.append(b'\x0a')#append the terminating line
        #send it to next part of the program
        self.append_orb_basic_fragment(area,code_list)




