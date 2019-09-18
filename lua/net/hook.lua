-----------------------------------------hook注册函数------------------------------

package.path = package.path .. ";src/"

-- 字符串分割
local function split(str, delimiter)
	if str==nil or str=='' or delimiter==nil then
		return nil
	end

	local result = {}
	for match in (str..delimiter):gmatch("(.-)"..delimiter) do
		table.insert(result, match)
	end
	return result
end

-- 表格合并
function table.merge(dest, src)
	for _,v in ipairs(src) do
		table.insert(dest, v)
	end
end

-- 测试调用，需被调用函数暴露在_G环境
local function wiz(cmd)
	local res = {test = ""}
	res["test"] = loadstring("return " .. cmd)()
	return res
end

-- 注册调用函数
local hook = {
	test = wiz,
}

return hook