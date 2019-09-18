-------------------------------------注册分发逻辑-----------------------------------

-- 注册分发类
Dispatcher = {
	cmd_tables = {}
}

function Dispatcher:new(o)
	o = o or {}
	setmetatable(o, self)
	self.__index = self
	return o
end

-- 注册单个执行函数
function Dispatcher:register(f, func)
	self.cmd_tables[f] = func
end

-- 注册多个执行函数
function Dispatcher:registers(funcs)
	for i, v in pairs(funcs) do
		self:register(i, v)
	end
end

-- 执行注册函数
function Dispatcher:handle(client, msg)
	if type(msg) == "table" then
		local func = msg["func"]
		local sid = msg["sid"]
		local args = msg["args"]
		local res = nil

		if func and args then
			local f = self.cmd_tables[func]

			if f then
				xpcall(function()
					res = f(unpack(args))
				end, function(msg)
					res = {err=msg, errinfo=msg}
				end)
				client:call_client(sid, res)
			elseif client then
				client:call_client(sid, {err="no handle function!", errinfo="no registered function in rpc server!"})
			end
		end
	end
end

return Dispatcher