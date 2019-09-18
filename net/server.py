# -*- coding:utf-8 -*-
u"""socket服务."""

import json
import time
import socket
import base64
import hashlib
import selectors
import traceback
from net.conf import config
from net.client import Client
from net.dispatcher import Dispatcher


class Mgr(object):
	u"""socket服务调度管理."""
	
	server = None
	is_run = False
	mgr = Dispatcher()

	def start(self, port):
		u"""启动监听服务."""
		self.is_run = True
		self.server = SocketServer()
		self.server.startup(ip="0.0.0.0", port=port)
		self.register()
		self.listen()

	def update(self):
		u"""主循环."""
		try:
			prev = time.time()
			self.process()
			cur = time.time()
			if (cur - prev) < 0.033:
				time.sleep(0.033 + prev - cur)
		except Exception:
			print(traceback.format_exc())

	def listen(self):
		u"""监听主循环事件."""
		while self.is_run:
			self.update()
	
	def stop(self):
		u"""关闭监听服务."""
		self.is_run = False
		if self.server:
			try:
				self.server.shutdown()
				self.server = None
			except Exception:
				print(traceback.format_exc())

	def restart(self, port):
		u"""重启服务."""
		self.stop()
		self.start(port)
	
	def register(self):
		u"""注册函数."""
		cmd_tables = {
			"count": self.server.count_clients,
		}
		self.mgr.registers(cmd_tables)

	def process(self):
		u"""事件处理逻辑."""
		if self.is_run:
			self.server.process()
			res = [-1, 0, ""]
			res[0], res[1], res[2] = self.server.read()

			if res[0] != -1:
				if config.DEBUG:
					print("[Debug] %s, %s, %s" % (res[0], res[1].get_cid(), res[2]))
				if res[0] == config.NET_CONNECTION_DATA:
					try:
						data = json.loads(res[2])
						if data:
							self.mgr.handle(res[1], data)
					except Exception:
						print(traceback.format_exc())
				else:
					print("%s, %s, %s" % (res[0], res[1].get_cid(), res[2]))


class SocketServer(object):
	u"""Server Logic."""
	
	server = None
	
	def __init__(self, timeout=config.CLIENT_TIMEOUT):
		super(SocketServer, self).__init__()
		self.host = 0
		self.port = 0
		self.count = 0
		self.index = 1
		self.timeout = timeout
		self.last_check_time = 0
		self.state = config.NET_STATE_STOP
		
		self.sock = None
		self.queue = []
		self.clients = []
		self.active_clients = {}
		self.sel = selectors.DefaultSelector()
		SocketServer.server = self
	
	def startup(self, ip="0.0.0.0", port=34567):
		u"""启动socket服务监听."""
		self.shutdown()
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		try:
			self.sock.bind((ip, port))
		except:
			print(traceback.format_exc())
			try:
				self.sock.close()
			except:
				print("Server close with exception!")
			return -1
		
		self.sock.listen(config.MAX_HOST_CLIENTS_INDEX + 1)
		self.sock.setblocking(False)
		self.port = self.sock.getsockname()[1]
		self.state = config.NET_STATE_ESTABLISHED
		self.sel.register(self.sock, selectors.EVENT_READ, self.handle_accept)
		print("Server %s:%d start listening!" % (ip, port))
		return 0
	
	def shutdown(self):
		u"""关闭socket服务."""
		if self.sock:
			try:
				self.sel.unregister(self.sock)
				self.sock.close()
			except:
				print("Server shutdown with exception!")

		for client in self.clients:
			if not client:
				continue
			try:
				client.close()
				del client
			except:
				print("Client shutdown with exception!")
		self.sock = None
		self.count = 0
		self.index = 1
		self.queue = []
		self.clients = []
		self.state = config.NET_STATE_STOP
		return

	def generate_id(self):
		u"""生成客户端ID."""
		pos = len(self.clients)
		if pos < 10000:
			self.clients.append(None)
		else:
			for i in xrange(len(self.clients)):
				if self.clients[i] is None:
					pos = i
					break
		# 下32位存储pos数值，上32位存储index
		cid = (pos & config.MAX_HOST_CLIENTS_INDEX) | (self.index << config.MAX_HOST_CLIENTS_BYTES)
		self.index += 1
		if self.index >= config.MAX_HOST_CLIENTS_INDEX:
			self.index = 1
		return cid, pos

	def get_client(self, cid):
		u"""获取客户端封装对象."""
		pos = cid & config.MAX_HOST_CLIENTS_INDEX
		if (pos < 0) or (pos >= len(self.clients)):
			return -1, None
		client = self.clients[pos]
		if client is None:
			return -2, None
		if client.cid != cid:
			return -3, None
		return 0, client
	
	def client_nodelay(self, cid, nodelay=0):
		u"""设置客户端阻塞模式."""
		code, client = self.get_client(cid)
		if code < 0:
			return code
		return client.set_nodelay(nodelay)
	
	def close_client(self, cid):
		u"""关闭客户端."""
		code, client = self.get_client(cid)
		if code < 0:
			return code
		client.close()
		del client
		return 0
	
	def count_clients(self, mold=config.PROT_SOCKET):
		u"""存活客户端."""
		cnt = 0
		for client in self.clients:
			if not client:
				continue
			if client.mold == mold:
				if client.status == config.NET_STATE_ESTABLISHED:
					cnt += 1
		return {"count": cnt}
	
	def send_client(self, cid, data):
		u"""向客户端发送一条消息."""
		code, client = self.get_client(cid)
		if code < 0:
			return code
		client.send(data)
		client.process()
		return 0

	def send_clients(self, mold, func, args):
		u"""分类型消息广播."""
		for client in self.clients:
			if not client:
				continue
			if client.mold == mold:
				client.call_client(func, args)
				client.process()
		return 0

	def read(self):
		u"""读取一个事件.
		
		type, cid, data.
		"""
		if len(self.queue) == 0:
			return -1, 0, ""
		event = self.queue[0]
		self.queue = self.queue[1:]
		return event
	
	def __parse_header(self, shake):
		u"""websocket握手协议header解析."""
		headers = {}
		# 原则上应该先按\r\r再按\r切分，此处为了兼容异常格式进行如下替换
		shake = shake.replace("\r\n", "$$")
		shake = shake.replace("\r\r", "$$")
		shake = shake.replace("\r", "$$")
		for line in shake.split("$$")[1:]:
			if ":" in line:
				key, value = line.split(":", 1)
				headers[key] = value
		return headers
	
	def __make_response(self, headers):
		u"""websocket握手协议回复内容生成."""
		sz_origin = headers['Origin'].lstrip()
		sz_key = base64.encodestring(hashlib.new('sha1', (headers['Sec-WebSocket-Key'].lstrip() + config.WS_SHAKE_KEY).encode("utf8")).digest()).decode("utf8")
		sz_host = headers['Host'].lstrip()
		print("new hanshake-->" + sz_host)
		response = "HTTP/1.1 101 Switching Protocols\r\n"
		response += "Upgrade: websocket\r\nConnection: Upgrade\r\n"
		response += "Sec-WebSocket-Accept: %s" % (sz_key,)
		response += "WebSocket-Origin: %s\r\n" % (sz_origin,)
		response += "WebSocket-Location: ws://%s/\r\n\r\n" % (sz_host,)
		return response
	
	def handshake(self, client, remote=None):
		u"""Websocket握手处理."""
		try:
			client.setblocking(1)
			shake = client.recv(1024)
			if not len(shake):
				return -1
			shake = shake.decode("utf8")
			headers = self.__parse_header(shake)
			if "Sec-WebSocket-Key" not in headers:
				# socket协议
				if headers.get("Sec-Socket-Key") == config.SEC_SOCKET_KEY:
					return config.PROT_SOCKET
				print("Sec socket key error!")
				client.close()
				return -1
		except Exception:
			print(traceback.format_exc())
			return -1
		
		try:
			# websocket协议
			response = self.__make_response(headers)
			print(response)
			client.send(response.encode("utf8"))
			return 1
		except Exception:
			print(traceback.format_exc())
			try:
				client.close()
			except:
				print(traceback.format_exc())
		return -1
	
	def gen_new_client(self, prot, sock):
		u"""生成新的客户端对象."""
		current = time.time()
		cid, pos = self.generate_id()
		client = Client()
		client.mold = prot
		client.assign(sock)
		client.cid = cid
		client.active = current
		client.peername = sock.getpeername()
		client.register_server(self)
		self.count += 1
		self.clients[pos] = client
		self.queue.append((config.NET_CONNECTION_ENTER, client, repr(client.peername)))
		self.sel.register(client.sock, selectors.EVENT_READ, client.record_read)

	def handle_accept(self, ssock, mask):
		u"""处理新的连接."""
		sock = None
		try:
			sock, remote = ssock.accept()
			print("remote", remote)
			sock.setblocking(False)
		except socket.error as e:
			if e.errno not in [11, 10035]:
				print(traceback.format_exc())
		
		if not sock:
			return
		if self.count > config.MAX_HOST_CLIENTS_INDEX:
			try:
				sock.close()
			except Exception:
				print("Clients count is up bound max host clients num, close sock error!")
			sock = None
		
		prot = self.handshake(sock, remote[0])
		if prot == -1:
			print("handshake failed!")
			return
		print("handshake success!")
		print("new client connected...<-- %s:%s" % (remote[0], remote[1]))
		self.gen_new_client(prot, sock)
	
	def __check_timeout(self, pos, current, client):
		u"""处理客户端超时."""
		timeout = current - client.active
		client_closed = (client.status == config.NET_STATE_STOP)
		is_timeout = (timeout >= self.timeout)
		errstr = "client is timeout!"
		if is_timeout or client_closed:
			if client_closed:
				errstr = "client closed connection!"
			self.queue.append((config.NET_CONNECTION_LEAVE, client, errstr))
			self.clients[pos] = None
			client.close()
			del client
			self.count -= 1

	def update_clients(self, current):
		u"""轮询客户端事件.
		
		for py2.
		"""
		for pos in range(len(self.clients)):
			client = self.clients[pos]
			if not client:
				continue
			client.process()
			while client.status == config.NET_STATE_ESTABLISHED:
				# 从接收缓冲区接收一条完整消息
				data = client.recv()
				if data == "":
					break
				# 添加一条完整消息到事件队列
				self.queue.append((config.NET_CONNECTION_DATA, client, data))
				client.active = current
			self.__check_timeout(pos, current, client)
	
	def update_events(self, current):
		u"""处理读事件.
		
		for py3.
		"""
		for (cid, client) in self.active_clients.items():
			if not client:
				continue
			client.process()
			while client.status == config.NET_STATE_ESTABLISHED:
				data = client.recv()
				if data == "":
					break
				# 添加一条完整消息到事件队列
				self.queue.append((config.NET_CONNECTION_DATA, client, data))
				client.active = current
		self.active_clients = {}

	def process(self):
		u"""接收并处理客户端数据."""
		current = time.time()
		if self.state != config.NET_STATE_ESTABLISHED:
			return 0
		# self.handle_accept(current)
		# self.update_clients(current)
		if current - self.last_check_time > self.timeout:
			self.last_check_time = current
			self.update_clients(current)
		else:
			self.update_events(current)
		events = self.sel.select()
		for key,mask in events:
			callback = key.data
			# print(callback.__name__)
			callback(key.fileobj, mask) 
		return 1