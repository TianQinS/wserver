----------------------------------- socket服务封装---------------------------------

local socket = require("socket")
local config = require("net/config")
local json = require("net/basic/dkjson")
local struct = require("net/basic/struct")
local hook = require("net/hook")
local Client = require("net/client")
local Dispatcher = require("net/dispatcher")

----------------------------------socket服务定义------------------------------
local SocketServer = {
	count = 0,
	sock = nil,
	queue = {},
	clients = {},
	port = 33455,
	timeout = config.HEART_TIMEOUT,
	state = config.NET_STATE_STOP
}

function SocketServer:new(o)
	o = o or {}
	setmetatable(o, self)
	self.__index = self
	return o
end

----------------------------------socket服务调度管理------------------------------
local Mgr = {
	server = nil,
	mgr = Dispatcher:new(),
	is_run = false
}

function Mgr:new(o)
	o = o or {}
	setmetatable(o, self)
	self.__index = self
	return o
end

-- 执行函数注册
function Mgr:register()
	self.mgr:registers(hook)
end

-- 启动监听服务
function Mgr:start(port)
	self.server = SocketServer:new()
	self.server:startup(port)
	self:register()
	self.is_run = true
end

-- 主循环
function Mgr:update()
	-- print("update")
	if self.is_run then
		xpcall(function()
			self:process()
		end, function(msg)
			print(debug.traceback() .. "\n" .. msg)
		end)
	else
		print(os.date("%Y-%m-%d %H:%M:%S", os.time()), "Socket connect failed!")
	end
end

-- 关闭监听服务
function Mgr:stop()
	self.is_run = false
	if self.server then
		xpcall(function()
			self.server:shutdown()
			self.server = nil
		end, function(msg)
			print(debug.traceback() .. "\n" .. msg)
		end)
	end
end

-- 启动服务
function Mgr:restart(port)
	self:stop()
	self:start(port)
	while self.is_run do
		local prev = os.time()
		self:update()
		local cur = os.time()
		if cur - prev < 0.033 then
			socket.select(nil, nil, 0.033 + prev - cur)
		end
	end
end

-- 事件处理逻辑
function Mgr:process()
	if self.is_run then
		self.server:process()
		local res = self.server:read()
		if res[1] == config.NET_CONNECTION_DATA then
			print(res[1], res[2], res[3])
			xpcall(function()
				local client = res[2]
				local data = json.decode(res[3])
				if data and client then
					self.mgr:handle(client, data)
				end
			end, function(msg)
				print(res[3])
				print(debug.traceback() .. "\n" .. msg)
			end)
		elseif res[1] >= 0 then
			print(res[1], res[3])
		end
	end
end

----------------------------------Server Logic--------------------------------------

-- 组织客户端id
function SocketServer:generate_id()
	local pos = table.getn(self.clients) + 1
	if pos < 1000 then
		self.clients[pos] = "None"
	else
		for i, v in pairs(self.clients) do
			if v == "None" then
				pos = i
				break
			end
		end
	end
	return pos
end

-- 读取一个事件
function SocketServer:read()
	if table.getn(self.queue) == 0 then
		-- type, cid, data
		return {-1, 0, ""}
	end
	local event = self.queue[1]
	table.remove(self.queue, 1)
	return event
end

-- 关闭socket服务
function SocketServer:shutdown()
	if self.sock ~= nil then
		xpcall(function()
			self.sock:close()
		end, function(msg)
			print("server shutdown with exception!")
		end)
		self.sock = nil
	end
	
	for i, v in pairs(self.clients) do
		if (v ~= "None") then
			xpcall(function()
				v:close()
				v = nil
			end, function(msg)
				print("client shutdown with exception!")
			end)
		end
	end

	self.count = 0	
	self.clients = {}
	self.queue = {}
	self.state = config.NET_STATE_STOP
end

-- 开启监听服务
function SocketServer:startup(port)
	port = port or self.port
	self:shutdown()
	self.sock = socket.tcp()
	xpcall(function()
		self.sock:bind("0.0.0.0", port)
		self.sock:settimeout(0)
		self.sock:listen(config.MAX_HOST_CLIENTS_INDEX + 1)
		self.state = config.NET_STATE_ESTABLISHED
		print(string.format("socket server %s start listening!", self.sock:getsockname()))
	end, function(msg)
		print(msg)
	end)
end

-- 获取客户端封装对象
function SocketServer:get_client(cid)
	local client = self.clients[cid]
	if (client == nil) or (client == "None") or (client.cid ~= cid) then
		return -1, nil
	end
	return 0, client
end

-- 关闭客户端
function SocketServer:close_client(self, cid)
	local code, client = self:get_client(cid)
	if code < 0 then
		return code
	end
	client:close()
	client = "None"
end

-- 向客户发送一条消息
function SocketServer:send_client(cid, data)
	local code, client = self:get_client(cid)
	if code < 0 then
		return code
	end
	client:send(data)
	client:process()
	return 0
end

-- 广播消息
function SocketServer:send_clients(func, args)
	for i, v in pairs(self.clients) do
		if v ~= "None" then
			v:call_client(func, args)
			v:process()
		end
	end
end

-- 统计存活客户端
function SocketServer:count_clients()
	local ct = 0
	for i, v in pairs(self.clients) do
		if v ~= "None" then
			ct = ct + 1
		end
	end
	return {count = ct}
end

-- 设置客户端阻塞模式
function SocketServer:client_nodelay(cid, nodelay)
	nodelay = nodelay or 0
	local code, client = self:get_client(cid)
	if code < 0 then
		return code
	end
	return client:nodelay(nodelay)
end

-- 握手处理
function SocketServer:handshake(client)
	local res = 0
	xpcall(function()
		-- client:settimeout(0)
		local chunk, status, partial = client:receive(100)
		print(chunk, status)
		if chunk == nil then
			res = -1
			return
		end
		local st, ed = string.find(chunk, config.SEC_SOCKET_KEY)
		if st then
			return
		end
		client:close()
		res = -1  
	end, function(msg)
		print(msg)
	end)
	return res
end

-- 新客户端连接
function SocketServer:handle_accept(current)
	local sock = nil
	xpcall(function()
		sock = self.sock:accept()
		if sock then
			print(sock:getpeername())
		end
	end, function(msg)
		print(msg)
	end)
	
	if (not sock) then
		return
	elseif self.count > config.MAX_HOST_CLIENTS_INDEX then
		xpcall(function()
			sock:close()
		end, function(msg)
			print(msg)
		end)
		sock = nil
	end
	local ctag = self:handshake(sock)
	if ctag == -1 then
		print("handshake failed!")
		return
	end
	
	print("handshake sucess!")
	print(string.format("new client connected...<- %s", sock:getpeername()))
	local cid = self:generate_id()
	local client = Client:new()
	client:assign(sock)
	client.cid = cid
	client.peername = sock:getpeername()
	client.active = os.time()
	
	self.clients[cid] = client
	self.count = self.count + 1
	table.insert(self.queue, {config.NET_CONNECTION_ENTER, client, client.peername})
end

-- 轮询各客户端事件
function SocketServer:update_clients(current)
	for i,v in pairs(self.clients) do
		if v ~= "None" then
			v:process()
			while v.state == config.NET_STATE_ESTABLISHED do
				-- 从缓冲区接收一条完整消息
				local data = v:recv()
				if data == "" then
					break
				end
				-- 添加一条完整消息到事件队列
				table.insert(self.queue, {config.NET_CONNECTION_DATA, v, data})
				v.active = current
			end
			
			local is_timeout = ((current - v.active) > self.timeout)
			local is_closed = (v.state == config.NET_STATE_STOP)
			if is_timeout then
				table.insert(self.queue, {config.NET_CONNECTION_LEAVE, v, "client timeout!"})
			elseif is_closed then
				table.insert(self.queue, {config.NET_CONNECTION_LEAVE, v, "client closed connection!"})
			end
			if is_timeout or is_closed then
				v:close()
				v = nil
				self.clients[i] = "None"
				self.count = self.count - 1
			end
		end
	end
end

-- 接收并处理客户端数据
function SocketServer:process()
	local current = os.time()
	if self.state ~= config.NET_STATE_ESTABLISHED then
		return 0
	end
	self:handle_accept(current)
	self:update_clients(current)
	return 1
end

return Mgr