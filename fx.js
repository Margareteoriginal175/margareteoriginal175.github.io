(function(){
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var root = document.documentElement;
  root.style.colorScheme = 'dark';
  root.classList.add('js');
  try { document.body.classList.add('page-enter'); } catch(e) {}
  var mobile = Math.min(window.innerWidth, window.innerHeight) < 720;

  /* ---------- GLSL shader background (raw WebGL, no deps) ---------- */
  (function shaderBg(){
    var old = document.getElementById('fx-particles'); if (old) old.style.display = 'none';
    var cv = document.getElementById('fx-shader');
    if (!cv) { cv = document.createElement('canvas'); cv.id = 'fx-shader'; cv.setAttribute('aria-hidden','true'); document.body.insertBefore(cv, document.body.firstChild); }
    var gl = cv.getContext('webgl', {antialias:false, alpha:false, premultipliedAlpha:false});
    if (!gl) { cv.classList.add('no-gl'); return; }
    var vs = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
    var fs = [
      'precision mediump float;uniform vec2 r;uniform float t;uniform vec2 m;uniform float sc;',
      'float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}',
      'float n(vec2 p){vec2 i=floor(p),f=fract(p);vec2 u=f*f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1,0)),u.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),u.x),u.y);}',
      'float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<5;i++){v+=a*n(p);p=p*2.03+vec2(1.7,9.2);a*=.5;}return v;}',
      'void main(){vec2 uv=gl_FragCoord.xy/r;vec2 p=(gl_FragCoord.xy-.5*r)/r.y;',
      'p.y+=sc*.35;float tt=t*.045;',
      'vec2 q=vec2(fbm(p*1.6+tt),fbm(p*1.6-tt+3.1));',
      'vec2 w=vec2(fbm(p*1.3+2.*q+vec2(1.7,9.2)+tt*1.3),fbm(p*1.3+2.*q+vec2(8.3,2.8)-tt));',
      'float f=fbm(p*1.2+2.4*w);',
      'vec3 bg=vec3(.010,.016,.040);',
      'vec3 c1=vec3(.36,.88,1.);vec3 c2=vec3(.65,.55,.98);vec3 c3=vec3(.37,.94,.75);',
      'vec3 col=bg;col=mix(col,c2*.5,smoothstep(.3,.95,f)*.65);',
      'col=mix(col,c1*.48,smoothstep(.45,1.,w.x)*.55);',
      'col+=c3*.10*smoothstep(.62,.95,q.y);',
      'float md=length(p-(m-.5)*vec2(r.x/r.y,1.));col+=c1*.10*exp(-md*md*5.);',
      'float vg=smoothstep(1.25,.25,length(uv-.5)*1.4);col*=.55+.45*vg;',
      'col*=.85;gl_FragColor=vec4(col,1.);}'
    ].join('\n');
    function sh(type, src){ var s=gl.createShader(type); gl.shaderSource(s,src); gl.compileShader(s); return s; }
    var pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) { cv.classList.add('no-gl'); return; }
    gl.useProgram(pr);
    var b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,3,-1,-1,3]), gl.STATIC_DRAW);
    var loc = gl.getAttribLocation(pr,'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
    var uR=gl.getUniformLocation(pr,'r'), uT=gl.getUniformLocation(pr,'t'), uM=gl.getUniformLocation(pr,'m'), uS=gl.getUniformLocation(pr,'sc');
    var scale = mobile ? 0.35 : 0.5, mx=.5, my=.5, smx=.5, smy=.5;
    function size(){ cv.width = Math.max(2, Math.floor(innerWidth*scale)); cv.height = Math.max(2, Math.floor(innerHeight*scale)); gl.viewport(0,0,cv.width,cv.height); }
    size(); window.addEventListener('resize', size);
    window.addEventListener('pointermove', function(e){ mx=e.clientX/innerWidth; my=1-e.clientY/innerHeight; }, {passive:true});
    var t0 = performance.now(), last = 0;
    function draw(now){
      smx += (mx-smx)*.04; smy += (my-smy)*.04;
      var sc = Math.min(1, (window.scrollY||0) / Math.max(1, document.documentElement.scrollHeight - innerHeight));
      gl.uniform2f(uR, cv.width, cv.height); gl.uniform1f(uT, (now-t0)/1000 + 20.0); gl.uniform2f(uM, smx, smy); gl.uniform1f(uS, sc);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
    if (reduced) { draw(performance.now()); return; }
    (function loop(now){
      requestAnimationFrame(loop);
      if (document.hidden || now - last < 33) return; last = now; draw(now);
    })(performance.now());
    cv.classList.add('on');
  })();

  /* ---------- pointer spotlight vars ---------- */
  window.addEventListener('pointermove', function(e){
    root.style.setProperty('--spot-x', e.clientX + 'px');
    root.style.setProperty('--spot-y', e.clientY + 'px');
  }, {passive:true});

  function bindGlow(el, tilt){
    el.addEventListener('pointermove', function(e){
      var r = el.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
      el.style.setProperty('--mx', (x*100)+'%'); el.style.setProperty('--my', (y*100)+'%');
      if (tilt && !reduced) el.style.transform = 'perspective(1000px) rotateX(' + ((0.5-y)*5) + 'deg) rotateY(' + ((x-0.5)*6) + 'deg) translateY(-3px)';
    });
    el.addEventListener('pointerleave', function(){ el.style.transform = ''; });
  }
  Array.prototype.forEach.call(document.querySelectorAll('.module-tile, .pin-card'), function(el){ bindGlow(el, true); });
  Array.prototype.forEach.call(document.querySelectorAll('.card, .panel-box, .term-block'), function(el){ bindGlow(el, false); });

  /* ---------- nav shrink on scroll + parallax ---------- */
  var nav = document.querySelector('.topnav');
  var par = Array.prototype.slice.call(document.querySelectorAll('[data-parallax]'));
  var ticking = false;
  function onScroll(){
    ticking = false;
    var y = window.scrollY || 0;
    if (nav) nav.classList.toggle('scrolled', y > 24);
    if (!reduced) par.forEach(function(el){
      var f = parseFloat(el.getAttribute('data-parallax')) || 0.2;
      el.style.transform = 'translate3d(0,' + (y*f).toFixed(1) + 'px,0)';
      if (el.hasAttribute('data-fade')) el.style.opacity = String(Math.max(0, 1 - y/ (innerHeight*0.9)));
    });
  }
  window.addEventListener('scroll', function(){ if (!ticking){ ticking = true; requestAnimationFrame(onScroll); } }, {passive:true});
  onScroll();

  /* ---------- count up when visible ---------- */
  function animateCount(el, target){
    var t0 = performance.now(), dur = 1400;
    function frame(t){
      var p = Math.min(1, (t - t0)/dur), e = 1 - Math.pow(1-p, 4);
      el.textContent = String(Math.round(target * e));
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  var counters = Array.prototype.slice.call(document.querySelectorAll('[data-count]'));
  if (!reduced && 'IntersectionObserver' in window) {
    var cio = new IntersectionObserver(function(en){ en.forEach(function(e){ if (e.isIntersecting){ animateCount(e.target, parseInt(e.target.getAttribute('data-count')||'0',10)); cio.unobserve(e.target);} }); }, {threshold:.3});
    counters.forEach(function(el){ cio.observe(el); });
  }

  /* ---------- live clock + countdown to next hourly build (:07 Beijing) ---------- */
  var clocks = document.querySelectorAll('[data-clock]'), nexts = document.querySelectorAll('[data-next]');
  function pad(n){ return (n<10?'0':'') + n; }
  function tick(){
    var now = new Date(), bj = new Date(now.getTime() + (now.getTimezoneOffset() + 480) * 60000);
    var s = pad(bj.getHours()) + ':' + pad(bj.getMinutes()) + ':' + pad(bj.getSeconds());
    Array.prototype.forEach.call(clocks, function(el){ el.textContent = s; });
    var m = bj.getMinutes(), sec = bj.getSeconds();
    var left = ((7 - m + 60) % 60) * 60 - sec; if (left <= 0) left += 3600;
    var txt = pad(Math.floor(left/60)) + ':' + pad(left%60);
    Array.prototype.forEach.call(nexts, function(el){ el.textContent = txt; });
  }
  if (clocks.length || nexts.length) { tick(); setInterval(tick, 1000); }

  /* ---------- scroll reveal with stagger ---------- */
  var reveals = Array.prototype.slice.call(document.querySelectorAll('.reveal, .card, .module-tile, .panel-box, .section > h2, .sec-head, .pin-card, .term-block'));
  reveals.forEach(function(el){
    el.classList.add('reveal');
    var sib = el.parentNode ? Array.prototype.indexOf.call(el.parentNode.children, el) : 0;
    el.style.setProperty('--d', Math.min(sib, 8) * 70 + 'ms');
  });
  if (!reduced && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(en){ if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
    }, {threshold: 0.08, rootMargin: '0px 0px -6% 0px'});
    reveals.forEach(function(el){ io.observe(el); });
  } else {
    reveals.forEach(function(el){ el.classList.add('in'); });
  }
})();
