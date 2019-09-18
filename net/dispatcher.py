# -*- coding:utf-8 -*-
u"""注册分发逻辑."""

import traceback
from net.conf import config


class Dispatcher(object):
	u"""调用函数注册分发."""
	
	def __init__(self):
		super(Dispatcher, self).__init__()
		self.cmd_tables = {}
	
	def rpc(self, route=""):
		"""rpc调用注册."""
		def decorator(f):
			fname = route if route != "" else f.__name__
			self.cmd_tables[fname] = f
			return f
		return decorator
	
	def register(self, f, func):
		u"""注册执行函数."""
		self.cmd_tables[f] = func
	
	def registers(self, funcs):
		for f in funcs:
			self.register(f, funcs[f])
		return 0
	
	def handle(self, client, msg):
		u"""执行注册函数.
		
		sid被设定为客户端消息标识，专用于callback使用.
		当用于websocket时，sid为客户端递增表示，用于保存的匿名函数.
		当用于socket时，sid可以为注册的callback函数，也可以为递增标识，用于缓存的callback函数.
		"""
		sid = msg.get("sid")
		args = msg.get("args", [])
		kwargs = msg.get("kwargs", {})
		func = msg.get("func")
		f = self.cmd_tables.get(func)

		if f:
			try:
				res = f(*args, **kwargs)
			except Exception:
				print(traceback.format_exc())
				if config.DEBUG:
					res = {"err": e.message, "errinfo": traceback.format_exc()}
			finally:
				if sid:
					client.call_client(sid, res)
		
	