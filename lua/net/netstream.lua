-------------------------字节流处理------------------------
local socket = require("socket")
local config = require("net/config")
local json = require("net/basic/dkjson")
local struct = require("net/basic/struct")

-------------------------封包解包处理----------------------
local Packet = {}

-- 仅支持socket
function Packet:new(o)
	o = o or {}
	setmetatable(o, self)
	self.__index = self
	return o
end

-- 读取字节内容
function Packet:read_bytes(data, st, ed)
	local ret = {}
	for i = st,ed do
		ret[i - st + 1] = string.byte(data, i)
	end
	return ret
end

-- 获取封包长度
function Packet:de_length(data)
	return struct.unpack(config.HEAD_LENGTH_FORMAT, string.sub(data, 1, config.HEAD_LENGTH_SIZE))
end

-- socket协议封包
function Packet:en_packet(data)
	return tostring(struct.pack(config.HEAD_LENGTH_FORMAT, string.len(data)))..data
end

-- socket协议解包
function Packet:de_packet(data)
	return string.sub(data, config.HEAD_LENGTH_SIZE + 1, string.len(data))
end

-----------------------------------字节流缓冲处理----------------------------------
local NetStream = Packet:new({
	sock = nil,
	send_buf = "",
	recv_buf = "",
	log_time = os.time(),
	state = config. NET_STATE_STOP
})

-- 创建sock对象
function NetStream:connect(address, port)
	self.send_buf = ""
	self.recv_buf = ""
	self.sock = socket.tcp()
	self.sock:connect(address, port)
	self.sock:settimeout(0)
	self.sock:setoption("keepalive", true)
	self.state = config.NET_STATE_CONNECTING
end

-- 关闭sock连接
function NetStream:close()
	self.state = config.NET_STATE_STOP
	if self.sock ~= nil then
		xpcall(function()
			self.sock:close()
		end, function(msg)
			print (msg)
		end)
	end
	self.sock = nil
end

-- 注册一个sock对象
function NetStream:assign(sock)
	self:close()
	self.send_buf = ""
	self.recv_buf = ""
	self.sock = sock
	self.sock:settimeout(0)
	self.state = config.NET_STATE_ESTABLISHED
end

-- 尝试连接
function NetStream:_tryConnect()
	if self.state == config.NET_STATE_ESTABLISHED then
		return 1
	elseif self.state ~= conf.NET_STATE_CONNECTING then
		return -1
	end
	
	if pcall(function()
		local chunk, status, partial = self.sock:receive(0)
		if status ~= "timeout" then
			print (status)
		else
			print ("connected")
		end
		if (status == "closed") or (status == "Not connected") then
			self:close()
		elseif status == "timeout" then
			self.recv_buf = ""
			self.state = config.NET_STATE_ESTABLISHED
		end
	end, function(msg)
		print (msg)
	end) then
		return 1
	end
end

-- 添加到发送缓冲区，并尝试发送数据
function NetStream:_sendRaw(data)
	self.send_buf = self.send_buf..data
	self:process()
end

-- 发送数据接口
function NetStream:send(data)
	local cur_time = os.time()
	data = self:en_packet(data)
	if cur_time >= self.log_time then
		self.log_time = cur_time
	end
	self:_sendRaw(data)
end

-- 从接收缓冲区取出固定长度数据
function NetStream:_recvRaw(size)
	local data = self:de_packet(string.sub(self.recv_buf, 1, size)) 
	self.recv_buf = string.sub(self.recv_buf, size + 1, string.len(self.recv_buf))
	return data
end

-- 接收缓冲区读出固定长度数据
function NetStream:_peekRaw(size)
	self:process()
	local length = string.len(self.recv_buf)
	if length == 0 then
		return ""
	elseif size > length then
		size = length
	end
	return string.sub(self.recv_buf, 1, size)
end

-- 接收一条完整消息
function NetStream:recv()
	local head = self:_peekRaw(config.HEAD_LENGTH_SIZE)
	if string.len(head) < config.HEAD_LENGTH_SIZE then
		return ""
	end
	local size = self:de_length(head)
	if size <= 0 then
		self:close()
		return ""
	elseif string.len(self.recv_buf) < size then
		return ""
	end
	return self:_recvRaw(size + config.HEAD_LENGTH_SIZE)
end

-- 从发送缓冲区发送数据
function NetStream:_trySend()
	local size = 0
	if string.len(self.send_buf) == 0 then
		return 0
	end
	xpcall(function()
		if string.len(self.send_buf) > config.MAX_SEND_LENGTH then
			local content = string.sub(self.send_buf, 1, config.MAX_SEND_LENGTH)
			size = self.sock:send(content)
		else
			size = self.sock:send(self.send_buf)
		end
	end, function(msg)
		print(msg)
	end)

	if size == nil then
		size = 0
	end
	self.send_buf = string.sub(self.send_buf, size + 1, string.len(self.send_buf))
	return size
end

-- 接收消息存入接收缓冲区
function NetStream:_tryRecv()
	local data = ""
	local receiving = true
	while receiving do
		local text = ""
		xpcall(function()
			local chunk, status, partial = self.sock:receive()
			if status == "timeout" then
				receiving = false
			elseif status == "closed" then
				self:close()
				receiving = false
			else
				text = chunk
			end
		end, function(msg)
			print(msg)
		end)
		if text ~= nil then
			data = data .. text
		end
	end
	
	local length = string.len(data)
	if length > 0 then
		self.recv_buf = self.recv_buf .. data
	end
	return length
end

-- socket消息处理.
function NetStream:process()
	if self.state == config.NET_STATE_STOP then
		return 0
	end
	if self.state == config.NET_STATE_CONNECTING then
		self:_tryConnect()
	elseif self.state == config.NET_STATE_ESTABLISHED then
		self:_tryRecv()
		self:_trySend()
	end
end

return NetStream