// 定义一个函数来检测是否为IE内核浏览器
function isIE() {
  const ua = window.navigator.userAgent
  // 检测Trident引擎（IE11及基于IE的浏览器）
  const isIE11 = ua.indexOf('Trident/') > 0 && ua.indexOf('rv:11.0') > 0
  // 检测旧的MSIE引擎（IE10及以下）
  const isOldIE = ua.indexOf('MSIE ') > 0
  // 如果任一条件为真，则认为是IE内核
  return isOldIE || isIE11
}

// 页面加载完成后执行
window.onload = function () {
  if (isIE()) {
    // 清空 app 元素的内容
    const appElement = document.getElementById('app')
    if (appElement) {
      appElement.innerHTML = ''
    }
    // 创建dom元素作为提示
    const lowBrowserDiv = document.createElement('div')
    lowBrowserDiv.style.cssText = 'position: fixed;width: 100%;height: 100%;background-color: #787779;top: 0;left: 0;z-index: 100;'
    const box = document.createElement('div')
    box.style.cssText = 'border: 1px solid #909399;width: 420px;height: 230px;position: absolute;top: 30%;left: 50%;margin-top: -100px;margin-left: -200px;background-color: #fff;padding: 20px 30px;text-align: center;box-sizing: border-box;border-radius: 4px;'
    const title = document.createElement('p')
    title.style.cssText = 'letter-spacing: 4px;font-size: 16px;font-weight: 600;'
    title.textContent = '重要提示'
    box.appendChild(title)
    const text = document.createElement('p')
    text.style.cssText = 'font-size: 14px;margin-top: 40px;line-height: 2;'
    text.textContent = 'IE 浏览器可能无法完全支持本产品的所有功能，为保障您的使用体验，请尝试使用除 IE 之外的主流浏览器，如 Edge 浏览器、Chrome 浏览器、Firefox 等。'
    box.appendChild(text)
    lowBrowserDiv.appendChild(box)
    document.body.appendChild(lowBrowserDiv)

  }
}
