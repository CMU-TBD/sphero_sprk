#!/usr/bin/python3

def cal_packet_checksum(arr):
	value = 0;
	for a in arr:
		for i in range(0,len(a)):
			value += a[i]
		#print(int.from_bytes(a,'big'))
		#print(value)
	return 255-(value%256)

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