# WServer
_**同时支持socket和websocket连接的服务端，附带精简rpc调用的客户端(python版和js版)和lua版socket服务.**_

## 使用范例

### 服务端
```python
	server = Mgr()
	server.start(23455)
	
	# 需要在此填充注册调用函数
	def register(self):
		u"""注册函数."""
		cmd_tables = {
			"count": self.server.count_clients,
		}
		self.mgr.registers(cmd_tables)
	
	# 相关调用函数原型
	def call_client(self, func, *args, **kwargs):
		u"""服务端rpc调用客户端注册函数.
		
		服务端rpc无回调处理.
		@param func: 客户端注册函数
		@param args: 参数列表
		@param kwargs: 参数字典
		"""
		pass
```

### 客户端Python
```python
	client = Client()
	client.register()
	client.start("127.0.0.1", 23455)
	# 调用服务端注册函数并将客户端注册函数作为callback回调
	client.call_server("count", "test", mold=config.PROT_WSOCKET)
	# 调用服务端注册函数并将客户端已有函数作为callback回调
	client.call_server("count", client.test, mold=config.PROT_SOCKET)
	# 不带回调函数
	client.call_server("count", None, mold=config.PROT_SOCKET)
	
	# 相关调用函数原型
	def call_server(self, func, callback, *args, **kwargs):
		u"""客户端rpc调用服务端注册api并且返回结果.

		可以设置回调函数，回调函数可以是注册的函数字符串标识，也可以直接是函数类型.
		@param func: 服务端注册函数
		@param callback: 回调函数
		@param args: 参数列表
		@param kwargs: 参数字典
		"""
		pass
```

### 客户端JavaScript
```javascript
	client.call_server({
		func: "count",
		args: [1],
		callback: function(data){
			alert(JSON.stringify(data));	
		}
	});
```