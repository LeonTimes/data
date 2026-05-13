!(function(c, b, d, a, o) {
    try{
        o = o || {};
        var s = typeof o.async !== 'undefined'? o.async : true;
        c[a] || (c[a] = {});
        c[a].config = Object.assign({
            pid: '',
            appType: "web",
            imgUrl: "https://arms-retcode.aliyuncs.com/r.png?",
            enableLinkTrace: true,
            behavior: true,
            enableSPA: true,
            useFmp: true,
            ignore: {
                ignoreApis: [/funlogs\/addfunlogs/]
            }
        }, o);
        with (b)
            with (body)
                with (insertBefore(createElement("script"), firstChild))
                    setAttribute("crossorigin", "", (src = d), (async = s));
    }catch(e){
        console.log('arms error :>> ', e);
    }
})(window, document, "https://retcode.alicdn.com/retcode/bl.js", "__bl", _arms);