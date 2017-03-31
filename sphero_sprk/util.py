#!/usr/bin/python3

from bluepy.btle import Scanner


def search_for_sphero(second_time=1):
	scanner = Scanner()
	devices = scanner.scan(second_time)
	sphero_list = []
	for dev in devices:
		#get the complete local name
		local_name = dev.getValueText(9)
		if local_name != None:
			if local_name.startswith('SK-'):
				sphero_list.append(dev.addr)
	return sphero_list


def cal_packet_checksum(arr):
	value = 0;
	for a in arr:
		for i in range(0,len(a)):
			value += a[i]
		#print(int.from_bytes(a,'big'))
		#print(value)
	return 255-(value%256)


def package_validator(data):
	if(len(data) < 5):
		return False
	if(data[0] != 255):
		return False

	#check dlen
	if(data[4] != 255):
		if(data[4] != len(data[4:-1])):
			return False

	#now we check the checksum
	data_pack = data[2:-1] #from DID to second last, exclude checksum
	checksum = cal_packet_checksum([data_pack])
	return (checksum == data[-1])



def OR_mask(b1, b2):
	if(len(b1) != len(b2)):
		raise Exception("OR bytes with different length")
	arr = []
	for i in range(0, len(b1)):
		arr.append(b1[i] | b2[i])
	return bytes(arr)

def XOR_mask(b1, b2):
	if(len(b1) != len(b2)):
		raise Exception("XOR bytes with different length")
	arr = []
	for i in range(0, len(b1)):
		arr.append(b1[i] ^ b2[i])
	return bytes(arr)

def count_data_size(arr_list):
	val = 0
	for l in arr_list:
		val += len(l)
	return val