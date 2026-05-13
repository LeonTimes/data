function addLink(url){
 	var link = document.createElement("link"),
 	heads = document.getElementsByTagName("head");   
    link.setAttribute("rel", "stylesheet");  
    link.setAttribute("type", "text/css");  
    link.setAttribute("href", url);  
    heads[0].appendChild(link);
}
function addScript(url,key){
	var script=document.createElement("script"),
	heads = document.getElementsByTagName("head");  
	script.setAttribute("type", "text/javascript");  
	script.setAttribute("src", url);  
	heads[0].appendChild(script)
}

var _nowString = (Date.now()+"").substring(0,9)

addLink("https://webresources.pkulaw.com/songyang/v6/main.css?"+_nowString)
addScript("https://webresources.pkulaw.com/songyang/v6/message.js?"+_nowString)

if(!window.axios){
	addScript("https://webresources.pkulaw.com/common/axios.js");
}
if(!window.Qs){
	addScript("https://webresources.pkulaw.com/common/qs.js");
}

function vueDome(){
	var div = document.createElement('div');
	div.id = 'sj-favorite';
	div.innerHTML = '<div><js-favorite ref="isVue"></js-favorite></div>';
	document.body.appendChild(div)
}
vueDome()

function start(){
	window.vueFavorite = new Vue({
		el: '#sj-favorite'
	}).$refs['isVue']
}
start()