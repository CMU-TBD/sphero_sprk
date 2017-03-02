#!/usr/bin/python3

import sys
import time
import binascii
import os

import bluepy
import yaml
from util import *

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
    def __init__(self, sphero_obj):
        bluepy.btle.DefaultDelegate.__init__(self)
        self._sphero_obj = sphero_obj
        self._callback_dict = {}
        self._wait_list = {}
        self._data_group_callback = {}
        self._enabled_group = []

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
            self._sphero_obj._device.waitForNotifications(1)
        return self._wait_list.pop(seq)

    def handleNotification(self, cHandle, data):
        #print("got notification with handle:{}".format(cHandle))
        #if(data[0] != 255):
            #raise Exception("Incoming package in wrong format")
        #print(data)
        if(len(data) >= 3 and data[0] == 255):
            if(data[1] == 255):
                #get the sequence number and check if a callback is assigned
                if(data[3] in self._callback_dict):
                    self.handle_callbacks(data)
                #check if we have it in the wait list
                if(data[3] in self._wait_list):
                    self._wait_list[data[3]] = data
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
            else:
                pass


class Sphero(object):

    RAW_MOTOR_MODE_OFF = "00"
    RAW_MOTOR_MODE_FORWARD = "01"
    RAW_MOTOR_MODE_REVERSE = "02"
    RAW_MOTOR_MODE_BRAKE = "03"
    RAW_MOTOR_MODE_IGNORE = "04"

    def __init__(self, addr):
        self._addr = addr
        self._connected = False
        self._seq_counter = 0
        self._stream_rate = 10
        #load the mask list
        with open(os.path.join(os.path.dirname(__file__),'..','res','mask_list.yaml'),'r') as mask_file:
            self._mask_list = yaml.load(mask_file)
        self._curr_data_mask = bytes.fromhex("0000 0000")

    def connect(self):
        """
        Connects the sphero with the address given in the constructor
        """
        self._device = bluepy.btle.Peripheral(self._addr, addrType=bluepy.btle.ADDR_TYPE_RANDOM)
        self._notifier = DelegateObj(self)
        self._device.setDelegate(self._notifier)
        self._devModeOn()
        self._connected = True #Might need to change to be a callback format
        #get the command service
        cmd_service = self._device.getServiceByUUID(RobotControlService)
        self._cmd_characteristics = {}
        characteristic_list = cmd_service.getCharacteristics()
        for characteristic in characteristic_list:
            uuid_str = binascii.b2a_hex(characteristic.uuid.binVal).decode('utf-8')
            self._cmd_characteristics[uuid_str] = characteristic
        
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

    def command(self, cmd, data):
        """
        cmd - (str) Hex String that is the command's code(ff, no need to put \\x in front)
        data - [bytes/str/int] an array of values with what to send. We will reformat int and string
        """

        data = self._format_data_array(data)
        sop1 = binascii.a2b_hex("ff")
        sop2 = binascii.a2b_hex("ff")
        did = binascii.a2b_hex("02")
        cid = binascii.a2b_hex(cmd)
        seq_val = self._get_sequence()
        seq = seq_val.to_bytes(1,"big")
        dlen = (count_data_size(data)+1).to_bytes(1,"big")#add one for checksum
        packet = [sop1,sop2,did,cid,seq,dlen] + data
        packet += [cal_packet_checksum(packet[2:]).to_bytes(1,'big')] #calculate the checksum
        #write the command to Sphero
        #print("cmd:{} packet:{}".format(cmd,b"".join(packet)))
        self._cmd_characteristics[CommandsCharacteristic].write(b"".join(packet)) 
        return seq_val      

    def sleep(self, timeout):
        """
        Sleep function that allows the notifications to be fired
        """
        startTime = time.time()
        while(time.time() - startTime <= timeout):
            self._device.waitForNotifications(1)


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


    def set_rgb_led(self, red, green, blue):
        """
        Set the color of Sphero's LED

        red - (int) Color of red in range 0-255
        green - (int) Color of green in range 0-255
        blue - (int) Color of blue in range 0-255
        """
        data = [red, green, blue, 0]
        self.command("20", data)

    def get_rgb_led(self):
        """
        Get the color of Sphero's LED
        ----
        return - tuple of the color in RGB
        """
        seq_num = self.command("22", [])
        response = self._notifier.wait_for_resp(seq_num)
        #parse the response packet and make sure it's correct
        if response and response[4] == 4:
            MRSP = response[2]
            red = response[5]
            green = response[6]
            blue = response[7]
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
        self.command("11",data)


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

    def set_stabilization(self,bool_flag):
        """
        Enable/Disable stabilization of Sphero

        bool_flag - (bool) stabilization on/off
        """
        data = ["01" if bool_flag else "00"]
        self.command("02",data)


    def set_raw_motor_values(self,lmode,lpower,rmode,rpower):
        """
        Set the raw motor values of Sphero
        lmode - (str) the hex string(without \\x) of the mode
        lpower - (int) the value of the power from 0-255
        rmode - (str) the hex string(without \\x) of the mode
        rpower - (int) the value of the power from 0-255
        """
        data = [lmode, lpower, rmode, rpower]
        self.command("33",data)

