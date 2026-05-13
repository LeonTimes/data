class iframeModule {
    constructor(obj,dom){
        this.dom = dom || document.body
        this.newElement = null
        this.handleMessage = null
        this.access_token = obj.access_token || ''
        this.BASE_URL = obj.BASE_URL || ''
        this.userInfo = obj.userInfo || {}
        this.platform = obj.platform===0 ? 0 : (obj.platform || 1)
        this.events = {}
    }
    create(data){
        this.newElement = document.createElement('iframe');
        this.newElement.src = this.BASE_URL+'iframe-module/'
        this.newElement.style.cssText = "background: transparent; border: none; width: 100vw; height: 100vh; position: fixed; left: 0; top: 0; z-index: 99997;"
        this.dom.appendChild(this.newElement);
        this.handleMessage = event => {
            let { code,res } = event.data
            if(code=='iframeModule'){
                if(res.type=='loading'){
                    this.messageFun({
                        type: 'start',
                        data: {
                            access_token: this.access_token,
                            userInfo: this.userInfo,
                            platform: this.platform
                        }
                    })
                    this.messageFun(data)
                }else{
                 	this.emit(res.type,res.data)
                    switch (res.type) {
                        case 'openYSF':
                            ysf('open')
                            break;
                        case 'closeIframe':
                        case 'contactusEnd':
                        case 'payEnd':
                            this.closeElement()
                            break;
                        default:
                            break;
                    }
                }
            }
        }
        window.addEventListener('message', this.handleMessage)
    }
    openModule(data){
        this.create(data)
    }
    messageFun(data){
        this.newElement.contentWindow.postMessage({
            code: 'iframeModule',
            res: data
        }, this.BASE_URL)
    }
    closeElement(){
        this.newElement.remove()
        this.newElement = null 
        window.removeEventListener('message', this.handleMessage);
        this.handleMessage = null
    }
    on(name,callback){
        if(!this.events[name]){
            this.events[name] = []
        }
        this.events[name].push(callback)
    }
    emit(name,data){
        if(this.events[name]){
            this.events[name].forEach(callback=>{
                if(typeof callback === 'function'){
                    callback(data)
                }
            })
        }
    }
    off(name,callback){
        const callbacks = this.events[name]
        if(callbacks){
            this.events[name] = callbacks.filter(item=>item!==callback)
        }
    }
}

// 支持多种导入方式
if (typeof module !== 'undefined' && module.exports) {
    // CommonJS 导出
    module.exports = iframeModule;
} else if (typeof window !== 'undefined') {
    // 浏览器全局变量
    window.iframeModule = iframeModule;
}
