# -*- coding:utf-8 -*-
u"""socket客户端."""

import json
import time
import threading
import traceback
from net.conf import config
from net.netstream import NetStream
from net.dispatcher import Dispatcher


class Client(NetStream):
	u"""socket客户端对象."""
	
	def __init__(self):
		super(Client, self).__init__()
		self.cid = -1
		self.cstate = config.ST_OFF
		self.active = time.time()
		self.current = time.time()
		self.server = None
		
		self.mgr = Dispatcher()
		self.sid = 0
		self.callbacks = {}
	
	def __eq__(self, other):
		return self.cid == other.cid
	
	def get_cid(self):
		return self.cid
	
	def set_cid(self, cid):
		self.cid = cid
	
	@property
	def alive(self):
		u"""客户端sock对象存活状态."""
		return self.status == config.NET_STATE_ESTABLISHED

	def close(self):
		if self.server:
			self.server.sel.unregister(self.sock)
		NetStream.close(self)
	
	def record_read(self, sock, mask):
		u"""记录读事件."""
		self.server.active_clients[self.cid] = self
	
	def register_server(self, server):
		u"""注册全局server对象."""
		self.server = server

	def test(self, *args, **kwargs):
		u"""测试调用函数."""
		print("[Test]", args, kwargs)
	
	def register(self):
		u"""注册调用函数."""
		cmd_tables = {
			"test": self.test,
		}
		self.mgr.registers(cmd_tables)
	
	def login(self):
		u"""登录注册函数."""
		s = "-:-\rSec-Socket-Key:%s\r\r\data" % (config.SEC_SOCKET_KEY)
		self.send(s)
	
	def heartbeat(self):
		u"""心跳函数."""
		h = {"func": "heartbeat", "args": [], "sid": -1}
		self.send(json.dumps(h))
	
	def call_client(self, func, *args, **kwargs):
		u"""服务端rpc调用客户端注册函数.
		
		服务端rpc无回调处理.
		@param func: 客户端注册函数
		@param args: 参数列表
		@param kwargs: 参数字典
		"""
		try:
			if self.status == config.NET_STATE_ESTABLISHED:
				self.send(json.dumps({"func": func, "args": args, "kwargs": kwargs}))
		except Exception:
			print(traceback.format_exc())

	def call_server(self, func, callback, *args, **kwargs):
		u"""客户端rpc调用服务端注册api并且返回结果.

		可以设置回调函数，回调函数可以是注册的函数字符串标识，也可以直接是函数类型.
		@param func: 服务端注册函数
		@param callback: 回调函数
		@param args: 参数列表
		@param kwargs: 参数字典
		"""
		sid = config.CLIENT_NO_CALLBACK_SID
		# 非注册函数缓存
		if callable(callback):
			self.sid += 1
			sid = self.sid
			self.callbacks[sid] = callback
		# 注册函数替换
		elif isinstance(callback, str) and len(callback) > 0:
			sid = callback
		# sid为0时为无回调
		self.send(json.dumps({"func": func, "args": args, "kwargs": kwargs, "sid": sid}))
	
	def handle(self, message):
		u"""调用处理."""
		if message.get("func"):
			sid = message.get("func")
			if isinstance(sid, int):
				func = self.callbacks.get(sid)
				if func:
					del self.callbacks[sid]
					# 如果是函数类型
					if callable(func):
						args = message.get("args", [])
						kwargs = message.get("kwargs", {})
						try:
							func(*args, **kwargs)
						except:
							print(traceback.format_exc())
						return			
			self.mgr.handle(self, message)			
			
	def __update(self):
		u"""处理心跳和消息逻辑."""
		heart_current = time.time()
		while self.status != config.NET_STATE_STOP:
			try:
				prev = time.time()
				self.process()
				ret = self.recv()
				if ret:
					message = json.loads(ret)
					self.handle(message)							
				
				cur = time.time()
				if (cur - prev) < 0.033:
					time.sleep(0.033 + prev - cur)
				if (cur - heart_current) > config.CLIENT_HEART_BEAT:
					self.heartbeat()
					heart_current = cur
			except:
				print(traceback.format_exc())
		print("Socket connect failed.")
	
	def __start(self, host, port):
		u"""启动socket客户端."""
		# print "host:", host, " port:", port
		self.connect(host, port)
		self.login()
		self.__update()
	
	def start(self, host, port):
		u"""启动客户端监听事件."""
		if self.status == config.NET_STATE_STOP:
			p = threading.Thread(target=self.__start, args=(host, int(port),))
			p.setDaemon(True)
			p.start()	