(function(){
  function ready(fn){
    if(document.readyState==='complete') fn();
    else window.addEventListener('load', fn, {once:true});
  }
  function boot(){
    var el=document.getElementById('brain-hero');
    if(!el) return;
    var reduced=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var start=function(){
      var canvasTest=document.createElement('canvas');
      var gl=canvasTest.getContext('webgl')||canvasTest.getContext('experimental-webgl');
      if(!gl || reduced){
        var s=document.createElement('script');
        s.src=(document.querySelector('meta[name="asset-base"]')||{}).content||'';
        // resolve relative vendor path from data attribute
        var base=el.getAttribute('data-vendor')||'vendor/';
        var f=document.createElement('script');
        f.src=base+'brain-fallback.js';
        f.onload=function(){ if(window.mountBrainFallback) window.mountBrainFallback(el); };
        document.head.appendChild(f);
        return;
      }
      var base=el.getAttribute('data-vendor')||'vendor/';
      import(new URL(base+'brain-hero.js', document.baseURI).href).then(function(mod){
        if(mod&&mod.mountBrainHero){
          var destroy=mod.mountBrainHero(el);
          if(!destroy){
            // fallback
            var f=document.createElement('script');
            f.src=base+'brain-fallback.js';
            f.onload=function(){ if(window.mountBrainFallback) window.mountBrainFallback(el); };
            document.head.appendChild(f);
          }
        }
      }).catch(function(){
        var f=document.createElement('script');
        f.src=base+'brain-fallback.js';
        f.onload=function(){ if(window.mountBrainFallback) window.mountBrainFallback(el); };
        document.head.appendChild(f);
      });
    };
    if('requestIdleCallback' in window) requestIdleCallback(start, {timeout:700});
    else setTimeout(start, 200);
  }
  ready(boot);
})();
