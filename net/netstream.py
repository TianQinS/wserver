# -*- coding:utf-8 -*-
u"""字节流处理."""

import sys
import time
import errno
import socket
import struct
import selectors
import traceback
from net.conf import config


class Packet(object):
	u"""封包解包处理.
	
	同步支持socket和websocket.
	"""
	
	def __init__(self):
		u"""初始协议类型为socket."""
		self.mold = config.PROT_SOCKET
		
	def try_encode(self, data):
		u"""统一编码为utf8."""
		try:
			data = data.decode("gbk")
		except:
			pass
		if isinstance(data, bytes):
			data = data.encode("utf-8", "ignore")
		return data
	
	def read_bytes(self, data, start, end):
		u"""读取字节内容."""
		bytes = data[start:end]
		if sys.version_info[0] < 3:
			bytes = map(ord, bytes)
		return bytes
	
	def __de_length_socket(self, data, recv_tag=False):
		u"""socket封包长度."""
		payload_length = struct.unpack(config.HEAD_LENGTH_FORMAT, data[:config.HEAD_LENGTH_SIZE])[0]
		return payload_length
	
	def __de_length_wsocket(self, data, recv_tag=False):
		u"""websocket封包长度."""
		b1, b2 = self.read_bytes(data, 0, 2)
		payload_length = b2 & config.WS_PAYLOAD_LEN
		opcode = b1 & config.WS_OPCODE
		masked = b2 & config.WS_MASKED
		
		if (not b1) or (opcode == config.WS_CLOSE_CONN):
			return -1
		if recv_tag and (not masked):
			return 0
		# 根据内容的长度分类型获取
		if payload_length == 126:
			payload_length = struct.unpack(">H", data[2:4])[0]
			return payload_length + 4
		elif payload_length == 127:
			payload_length = struct.unpack(">Q", data[2:10])[0]
			return payload_length + 10
		else:
			return payload_length + 2
	
	def de_length(self, data, recv_tag=False):
		u"""获取封包长度."""
		if self.mold == config.PROT_SOCKET:
			return self.__de_length_socket(data, recv_tag)
		return self.__de_length_wsocket(data, recv_tag)
	
	def __en_packet_socket(self, data):
		u"""socket协议封包."""
		length = struct.pack(config.HEAD_LENGTH_FORMAT, len(data))
		return length.decode() + data
	
	def __en_packet_wsocket(self, data):
		u"""websocket协议封包."""
		header = bytearray()
		length = len(data)
		header.append(config.WS_FIN | config.WS_OPCODE_TEXT)
		# 根据区间进行长度封包
		if length <= 125:
			header.append(length)
		elif length <= 65535:
			header.append(config.WS_PAYLOAD_LEN_EXT16)
			header.extend(struct.pack(">H", length))
		elif length < 18446744073709551616:
			header.append(config.WS_PAYLOAD_LEN_EXT64)
			header.extend(struct.pack(">Q", length))
		else:
			raise Exception("Message is too big, consider breaking it into chunks.")
			return
		
		data = "%s%s" % (header, data)
		return data
	
	def en_packet(self, data):
		u"""封包."""
		payload = self.try_encode(data)
		if self.mold == config.PROT_SOCKET:
			return self.__en_packet_socket(payload)
		return self.__en_packet_wsocket(payload)
	
	def __de_packet_socket(self, data):
		u"""socket协议解包."""
		return data[config.HEAD_LENGTH_SIZE:]
	
	def __de_packet_wsocket(self, data):
		u"""websocket协议解包."""
		mid = 0
		masks = ""
		b1, b2 = self.read_bytes(data, 0, 2)
		length = b2 & config.WS_PAYLOAD_LEN
		
		if length == 126:
			mid = 8
			masks = self.read_bytes(data, 4, 8)
			length = struct.unpack(">H", data[2:4])[0]
		elif length == 127:
			mid = 14
			masks = self.read_bytes(data, 10, 14)
			length = struct.unpack(">Q", data[2:10])[0]
		else:
			mid = 6
			masks = self.read_bytes(data, 2, 6)
		
		decoded = ""
		for char in self.read_bytes(data, mid, length + mid):
			char ^= masks[len(decoded) % 4]
			decoded += chr(char)
		return decoded
	
	def de_packet(self, data):
		u"""解包."""
		if self.mold == config.PROT_SOCKET:
			return self.__de_packet_socket(data)
		return self.__de_packet_wsocket(data)


class NetStream(Packet):
	u"""字节流缓冲处理."""
	
	def __init__(self):
		super(NetStream, self).__init__()
		self.sock = None
		self.send_buf = b""
		self.recv_buf = b""
		self.state = config.NET_STATE_STOP
		self.errc = 0
		self.conn = (errno.EISCONN, 10057, 10053)
		self.errd = (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK, 10035)
		self.log_time = time.time()
	
	@property
	def status(self):
		u"""获取socket连接状态."""
		return self.state
	
	def connect(self, address, port):
		u"""创建sock连接对象."""
		self.errc = 0
		self.send_buf = b""
		self.recv_buf = b""
		self.state = config.NET_STATE_CONNECTING

		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setblocking(0)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
		self.sock.connect_ex((address, port))
		return 0
	
	def close(self):
		u"""关闭sock对象连接."""
		self.state = config.NET_STATE_STOP
		if not self.sock:
			return 0
		try:
			self.sock.close()
		except Exception:
			print(traceback.format_exc())
		self.sock = None
		return 0
		
	def assign(self, sock):
		u"""注册一个sock对象."""
		self.close()
		self.send_buf = b""
		self.recv_buf = b""
		self.sock = sock
		self.sock.setblocking(0)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
		self.state = config.NET_STATE_ESTABLISHED
		return 0
	
	def set_nodelay(self, nodelay=0):
		u"""设置非阻塞模式."""
		if "TCP_NODELAY" not in socket.__dict__:
			return -1
		if self.status != 2:
			return -2
		self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, nodelay)
		return 0
	
	def __tryConnect(self):
		u"""更新连接状态."""
		if self.state == config.NET_STATE_ESTABLISHED:
			return 1
		if self.state != config.NET_STATE_CONNECTING:
			return -1
		try:
			self.sock.recv(0)
		except socket.error as e:
			code = e.errno
			print("connecting:", code)
			if code in self.conn:
				return 0
			if code in self.errd:
				self.recv_buf = b""
				self.state = config.NET_STATE_ESTABLISHED
				return 1
			self.close()
			return -1
		self.state = config.NET_STATE_ESTABLISHED
		return 1
	
	def __sendRaw(self, data):
		u"""添加到发送缓冲区，并尝试发送数据."""
		self.send_buf = self.send_buf + data.encode("utf8")
		self.process()
		return 0
	
	def send(self, data):
		u"""发送数据接口."""
		cur_time = time.time()
		data = self.en_packet(data)
		if cur_time >= self.log_time:
			self.log_time = cur_time
		self.__sendRaw(data)
		return 0
	
	def __recvRaw(self, size):
		u"""从接收缓冲区取出固定长度数据."""
		data = self.recv_buf[0:size]
		data = self.de_packet(data)
		self.recv_buf = self.recv_buf[size:]
		return data
	
	def __peekRaw(self, size):
		u"""从接收缓冲区读出固定长度数据."""
		self.process()
		if len(self.recv_buf) == 0:
			return ""
		if size > len(self.recv_buf):
			size = len(self.recv_buf)
		return self.recv_buf[0:size]
	
	def recv(self):
		u"""接收一条完整消息."""
		head = self.__peekRaw(10)
		if len(head) < 4:
			return ""
		size = self.de_length(head, True)
		if size <= 0:
			print("DeLength Error!")
			self.close()
			return ""
		if len(self.recv_buf) < size:
			return ""
		# print size, len(self.recv_buf)
		return self.__recvRaw(size + 4)
	
	def __trySend(self):
		u"""从发送缓冲区发送数据.
		
		直至阻塞或者达到系统缓冲限制.
		"""
		size = 0
		if len(self.send_buf) == 0:
			return 0
		try:
			size = self.sock.send(self.send_buf)
		except socket.error as e:
			code = e.errno
			if code not in self.errd:
				self.errc = code
				print(traceback.format_exc())
				self.close()
				return -1
		
		if config.DEBUG:
			print("[Debug][Send]", self.send_buf[:size])
		self.send_buf = self.send_buf[size:]
		return size
	
	def __tryRecv(self):
		u"""接收消息存入接收缓冲区."""
		data = b""
		while True:
			try:
				text = b""
				text = self.sock.recv(1024)
				if not text:
					self.errc = 10000
					self.close()
					return -1
			except socket.error as e:
				code = e.errno
				if code not in self.errd:
					print(traceback.format_exc())
					self.errc = code
					self.close()
					return -1
			if text == b"":
				break
			
			data = data + text
		if data:
			if config.DEBUG:
				print("[Debug][Recv]", data)
			self.recv_buf = self.recv_buf + data
		return len(data)
	
	def process(self):
		u"""socket消息处理."""
		if self.status == config.NET_STATE_STOP:
			return 0
		if self.status == config.NET_STATE_CONNECTING:
			self.__tryConnect()
		if self.status == config.NET_STATE_ESTABLISHED:
			self.__tryRecv()
		if self.status == config.NET_STATE_ESTABLISHED:
			self.__trySend()
		return 0