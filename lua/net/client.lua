-----------------------------------socket客户端------------------------------------
local config = require("net/config")
local json = require("net/basic/dkjson")
local netstream = require("net/netstream")


-- socket客户端对象
local Client = netstream:new({
	cid = -1,
	cstate = config.ST_OFF
})

-- 析构函数
function Client:delete()
	self:close()
end

function Client:__eq(a, b)
	if a.cid == b.cid then
		return true
	end
	return false
end

function Client:call_client(func, ...)
	local args = {...}
	xpcall(function()
		if self.state == config.NET_STATE_ESTABLISHED then
			self:send(json.encode({
				func = func,
				args = args
			}))
		end
	end, function(msg)
		print(debug.traceback() .. "\n" .. msg)
	end)
end

return Client