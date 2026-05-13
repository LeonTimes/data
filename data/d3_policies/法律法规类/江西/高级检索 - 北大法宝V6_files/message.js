function addLink(url){
    var link = document.createElement("link"),
    heads = document.getElementsByTagName("head");   
    link.setAttribute("rel", "stylesheet");  
    link.setAttribute("type", "text/css");  
    link.setAttribute("href", url);  
    heads[0].appendChild(link);
}

addLink("https://webresources.pkulaw.com/songyang/v6/message.css")

window.message = {
    time: 3000,
    url: {
        error: 'https://webresources.pkulaw.com/songyang/v6/error.png',
        success: 'https://webresources.pkulaw.com/songyang/v6/success.png'
    },
    error: function(html){
        this.html('error',html)
    },
    success: function(html){
        this.html('success',html)
    },
    start: function(dom){
        var div = document.getElementsByClassName('sj-message')
        for(var i=0; i<div.length; i++){
            div[i].style.display = 'none'
        }
        document.body.appendChild(dom)
        setTimeout(function(){
            dom.style.display = 'none'
        },this.time)
    },
    html: function(type,html){
        var div = document.createElement('div')
        div.className = 'sj-message' + ' '+'sj-' + type
        div.innerHTML = '<div><img src=' + this.url[type] +'>' + html + '</div>'
        this.start(div)
    }
}
