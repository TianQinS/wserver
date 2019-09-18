# -*- coding: utf8 -*-
u"""使用范例."""

import time
from net.conf import config
from net.server import Mgr
from net.client import Client
from net.utils import async_call

@async_call
def start_server():
	u"""启动服务端."""
	server = Mgr()
	server.start(23456)

def start_client():
	u"""启动客户端."""
	client = Client()
	client.register()
	client.start("127.0.0.1", 23456)
	return client

if __name__ == "__main__":
	u"""为了测试需要，子线程启动服务端."""	
	start_server()
	time.sleep(2)
	c = start_client()
	time.sleep(1)
	c.call_server("count", c.test, mold=config.PROT_SOCKET)
	time.sleep(1)
	c.call_server("count", "test", mold=config.PROT_WSOCKET)
	time.sleep(10)