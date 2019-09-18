window.Client=function Client(){this.sid=0};Client.prototype.process_msg=function(data){var args=data.args;if(typeof args=="string"){args=JSON.parse(args)}try{if(this.callbacks[data.func]){this.callbacks[data.func].apply(this,args);return}}catch(err){console.log(err.message)}eval(data.func).apply(null,args)};Client.prototype.connect=function(opts){var endpoint="ws://"+opts.host+":"+opts.port;var that=this;if(window.WebSocket){this._sock=new WebSocket(endpoint)}else{if(window.MozWebSocket){this._sock=MozWebSocket(endpoint)}else{opts.onError("Not Supported");return}}this._sock.onopen=function(){if(opts.onConnect){opts.onConnect()}};this._sock.onmessage=function(event){var data=JSON.parse(event.data.toString());if(data.error!=undefined){opts.onError(data.error)}else{that.process_msg(data)}};this._sock.onclose=function(event){if(opts.onClose){opts.onClose()}else{console.log("远端已经关闭")}}};Client.prototype.status=function(){var state=0;switch(this._sock.readyState){case 1:state=1;break;case 0:console.log("还没建立连接!");break;case 2:console.log("关闭连接中...");break;case 3:console.log("连接已关闭.");break;default:console.log("状态异常")}return state};Client.prototype.call_server=function(opts){if(this._sock==undefined){return}this.sid=this.sid+1;console.log(this.status());if(typeof(opts.callback)=="function"){if(!this.callbacks){this.callbacks={}}this.callbacks[this.sid]=opts.callback;opts.sid=this.sid}if(this.status()==1){console.log(JSON.stringify(opts).length);this._sock.send(JSON.stringify(opts))}};