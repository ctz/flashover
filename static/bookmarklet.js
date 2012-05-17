/*!
 * Flashover bookmarklet v1
 *
 * Public domain.
 */
 (function() {
    var base = 'http://flashover.ifihada.com/';
    var absoluteURL = function(url) {
        var escape = function(s) {
            return s.split('&').join('&amp;').split('<').join('&lt;').split('"').join('&quot;');
        }
        
        var el = document.createElement('div');
        el.innerHTML = '<a href="' + escape(url) + '">x</a>';
        return el.firstChild.href;
    };
    
    var absoluteLoc = function(el) {
        var left = 0;
        var top = 0;
        var height = el.offsetHeight;
        var width = el.offsetWidth;
        
        if (el.offsetParent) {
            while (el) {
                left += el.offsetLeft;
                top += el.offsetTop;
                el = el.offsetParent;
            }
        }
        
        return {left: left, top: top, height: height, width: width};
    };
    
    var info = function(msg) {
        var container = document.createElement('div');
        container.style.cssText = 'position: absolute; width: 30%; z-index: 100000; left: 35%; top: 0px; padding: 3px; border-bottom-left-radius: 5px; border-bottom-right-radius: 5px; background-color: #e44d26; font-face: sans-serif !important; font-size: 13px !important; color: white !important;';
        document.body.appendChild(container);
        container.innerHTML = msg;
    };
 
    var handle = function(el, mu) {
        var sz = 50;
        var pos = absoluteLoc(el);
        var container = document.createElement('div');
        container.style.position = 'absolute';
        container.style.width = sz + 'px';
        container.style.height = sz + 'px';
        container.style.zIndex = '100000';
        container.style.left = (pos.left - sz) + 'px';
        container.style.top = (pos.top + pos.height / 2 - sz / 2) + 'px';
        
        var button = document.createElement('a');
        button.href = base + 'bookmarklet-target?url=' + mu;
        button.title = 'View with flashover';
        
        var img = document.createElement('img');
        img.src = base + 'static/bookmarklet-image.png';
        img.style.width = sz + 'px';
        img.style.height = sz + 'px';
        img.style.borderWidth = 0;
        img.style.backgroundColor = '#e44d26';
        img.style.borderTopLeftRadius = '5px';
        img.style.borderBottomLeftRadius = '5px';
        
        button.appendChild(img);
        container.appendChild(button);
        document.body.appendChild(container);
        
        var shadow = '0px 0px 150px 10px #000';
        el.style.borderLeft = '2px solid #e44d26';
        el.style.borderRight = el.style.borderLeft;
        el.style.marginLeft = '-2px';
        el.style.marginRight = '-2px';
        el.style.webkitBoxShadow = shadow
        el.style.mozBoxShadow = shadow;
        el.style.boxShadow = shadow;
        el.style.zIndex = '10000000';
    };
    
    var typeOk = function(tt) {
        return tt === null || tt === '' || tt === 'application/x-shockwave-flash';
    };
    
    var classOk = function(cls) {
        return cls === null || cls === '' || tt.lower() === 'clsid:d27cdb6e-ae6d-11cf-96b8-444553540000';
    };
    
    var findMovie = function(node) {
        if (node.hasAttribute('data'))
            return node.getAttribute('data');
        for (var p in node.getElementsByTagName('param')) {
            if (p.getAttribute('name').lower() == 'movie')
                return p.getAttribute('value');
        }
    };
 
    var processed = 0;
    
    var processDoc = function(d) {
        var embeds = d.getElementsByTagName('embed');
        var objects = d.getElementsByTagName('objects');
        
        for (var i = 0; i < embeds.length; i++)
        {
            var e = embeds[i];
            if (typeOk(e.getAttribute('type')) && e.hasAttribute('src')) {
                handle(e, absoluteURL(e.getAttribute('src')));
                processed++;
            }
        }
        
        for (var i = 0; i < objects.length; i++)
        {
            var o = objects[i];
            if (typeOk(o.getAttribute('type')) ||
                classOk(o.getAttribute('classid'))) {
                handle(o, absoluteURL(findMovie(o)));
                processed++;
            }
        }
    };
    
    processDoc(document);
    if (processed > 0)
        info('Flash movies found in this frame have been marked with a flashover button.');
    else
        info("No flash movies found in this frame. Due to the same-origin policy, we can't see the contents of frames or iframes.");
 })();