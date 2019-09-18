# -*- coding:utf-8 -*-
u"""socket和websocket配置项."""


class Config(object):
	u"""网络配置项."""

	DEBUG = True

	# socket网络字节包头
	HEAD_LENGTH_FORMAT = "<I"
	HEAD_LENGTH_SIZE = 4

	# websocket网络字节包头
	WS_FIN = 0x80
	WS_OPCODE = 0x0f
	WS_MASKED = 0x80
	WS_PAYLOAD_LEN = 0x7f
	WS_PAYLOAD_LEN_EXT16 = 0x7e
	WS_PAYLOAD_LEN_EXT64 = 0x7f
	WS_OPCODE_TEXT = 0x01
	WS_CLOSE_CONN = 0x8
	# 握手标识
	WS_SHAKE_KEY = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

	# 协议类型
	PROT_SOCKET = 0
	PROT_WSOCKET = 1

	# 客户端超时断开
	CLIENT_TIMEOUT = 60000
	# 客户端心跳包冷却时间
	CLIENT_HEART_BEAT = 30000
	# 客户端无回调SID
	CLIENT_NO_CALLBACK_SID = 0 

	# 网络连接状态
	NET_STATE_STOP = 0
	NET_STATE_CONNECTING = 1
	NET_STATE_ESTABLISHED = 2
	NET_CONNECTION_ENTER = 0
	NET_CONNECTION_DATA = 1
	NET_CONNECTION_LEAVE = 2

	# 客户端状态
	ST_OFF = 0
	ST_IDLE = 1

	# 服务端连接数
	MAX_HOST_CLIENTS_INDEX = 16
	MAX_HOST_CLIENTS_BYTES = 16


class Development(Config):
	u"""调试配置."""

	# socket协议安全认证标识
	SEC_SOCKET_KEY = "test"

class Production(Config):
	u"""线上配置."""

	# socket协议安全认证标识
	SEC_SOCKET_KEY = ""


config = None
if Config.DEBUG:
	config = Development
else:
	config = Production