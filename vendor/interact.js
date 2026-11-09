(function(){
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var touch = matchMedia('(hover: none), (pointer: coarse)').matches;
  var desktop = !touch;

  /* toast */
  var toast = document.createElement('div');
  toast.id = 'fx-toast';
  toast.setAttribute('role','status');
  document.body.appendChild(toast);
  function showToast(msg){
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(function(){ toast.classList.remove('show'); }, 1800);
  }

  /* scroll progress + back to top */
  var bar = document.createElement('div'); bar.id = 'scroll-progress'; document.body.appendChild(bar);
  var topOrb = document.createElement('button');
  topOrb.id = 'back-top'; topOrb.type='button'; topOrb.setAttribute('aria-label','回到顶部'); topOrb.innerHTML='↑';
  document.body.appendChild(topOrb);
  topOrb.addEventListener('click', function(){ window.scrollTo({top:0, behavior: reduced?'auto':'smooth'}); });
  function onScroll(){
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    var p = max>0 ? (h.scrollTop/max) : 0;
    bar.style.transform = 'scaleX(' + p + ')';
    topOrb.classList.toggle('show', h.scrollTop > 480);
  }
  window.addEventListener('scroll', onScroll, {passive:true}); onScroll();

  /* custom cursor + trail (desktop) */
  if (desktop && !reduced) {
    document.documentElement.classList.add('has-cursor');
    var cur = document.createElement('div'); cur.id='cursor-dot'; document.body.appendChild(cur);
    var trail = [];
    for (var i=0;i<5;i++){ var t=document.createElement('div'); t.className='cursor-trail'; document.body.appendChild(t); trail.push(t); }
    var mx=0,my=0, pts=trail.map(function(){return {x:0,y:0};});
    window.addEventListener('pointermove', function(e){ mx=e.clientX; my=e.clientY; cur.style.transform='translate('+mx+'px,'+my+'px)'; }, {passive:true});
    (function loop(){
      var x=mx,y=my;
      for (var i=0;i<pts.length;i++){
        pts[i].x += (x - pts[i].x) * (0.35 - i*0.03);
        pts[i].y += (y - pts[i].y) * (0.35 - i*0.03);
        trail[i].style.transform='translate('+pts[i].x+'px,'+pts[i].y+'px) scale('+(1-i*0.08)+')';
        x=pts[i].x; y=pts[i].y;
      }
      requestAnimationFrame(loop);
    })();
  }

  /* magnetic tiles/buttons */
  if (desktop && !reduced) {
    var mags = document.querySelectorAll('.module-tile, .btn, .topnav a, #back-top');
    Array.prototype.forEach.call(mags, function(el){
      el.addEventListener('pointermove', function(e){
        var r=el.getBoundingClientRect();
        var dx=(e.clientX-(r.left+r.width/2))/r.width;
        var dy=(e.clientY-(r.top+r.height/2))/r.height;
        el.style.translate = (dx*12)+'px '+(dy*10)+'px';
      });
      el.addEventListener('pointerleave', function(){ el.style.translate=''; });
    });
  }

  /* module tile <-> brain region */
  Array.prototype.forEach.call(document.querySelectorAll('.module-tile'), function(el){
    el.addEventListener('pointerenter', function(){
      var href=(el.getAttribute('href')||'');
      var id=href.split('/').pop().replace('.html','');
      if (window.__brainAPI && window.__brainAPI.highlightRegion) window.__brainAPI.highlightRegion(id);
    });
    el.addEventListener('pointerleave', function(){
      if (window.__brainAPI && window.__brainAPI.highlightRegion) window.__brainAPI.highlightRegion('');
    });
  });

  /* card ripple + copy link */
  document.addEventListener('click', function(e){
    var card = e.target.closest && e.target.closest('.card, .module-tile');
    if (card && !reduced) {
      var r=card.getBoundingClientRect();
      var rip=document.createElement('span'); rip.className='ripple';
      rip.style.left=(e.clientX-r.left)+'px'; rip.style.top=(e.clientY-r.top)+'px';
      card.appendChild(rip); setTimeout(function(){ rip.remove(); }, 700);
    }
    var copyBtn = e.target.closest && e.target.closest('[data-copy-link]');
    if (copyBtn) {
      e.preventDefault();
      var url = copyBtn.getAttribute('data-copy-link') || location.href;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function(){ showToast('链接已复制'); }).catch(function(){ showToast('复制失败'); });
      } else {
        showToast('请手动复制链接');
      }
    }
  });

  /* text scramble on headings */
  function scramble(el){
    if (reduced || el.dataset.scrambled) return;
    el.dataset.scrambled='1';
    var final = el.textContent;
    var chars = 'アイウエオカキクケコABCDEF0123456789#$%';
    var i=0;
    var t=setInterval(function(){
      el.textContent = final.split('').map(function(ch, idx){
        if (idx < i) return final[idx];
        if (/\s/.test(ch)) return ch;
        return chars[Math.floor(Math.random()*chars.length)];
      }).join('');
      i += 1;
      if (i > final.length) { el.textContent=final; clearInterval(t); }
    }, 28);
  }
  if ('IntersectionObserver' in window) {
    var io=new IntersectionObserver(function(entries){
      entries.forEach(function(en){ if(en.isIntersecting){ scramble(en.target); io.unobserve(en.target);} });
    }, {threshold:0.4});
    document.querySelectorAll('h1.hero-title, .hero h1, .section h2').forEach(function(h){ if (!h.closest('[data-kinetic]') && !h.hasAttribute('data-kinetic') && !h.querySelector('*')) io.observe(h); });
  }

  /* Cmd/Ctrl+K command palette */
  var items = [];
  document.querySelectorAll('.card').forEach(function(card){
    var title = (card.querySelector('.title')||{}).textContent||'';
    var link = card.querySelector('a[href]');
    var href = link ? link.getAttribute('href') : '';
    var text = card.getAttribute('data-text')||title;
    items.push({title:title.trim(), href:href, text:text});
  });
  document.querySelectorAll('.module-tile').forEach(function(tile){
    items.push({title:(tile.querySelector('h2')||{}).textContent||'模块', href:tile.getAttribute('href')||'', text:tile.textContent||''});
  });
  var pal=document.createElement('div'); pal.id='cmd-palette'; pal.innerHTML='<div class="cmd-box"><input id="cmd-input" placeholder="搜索资源 / 模块…（Esc 关闭）" /><div id="cmd-results"></div></div>';
  document.body.appendChild(pal);
  var input=pal.querySelector('#cmd-input');
  var results=pal.querySelector('#cmd-results');
  function render(q){
    q=(q||'').trim().toLowerCase();
    var hits=items.filter(function(it){ return !q || (it.text+it.title).toLowerCase().indexOf(q)>=0; }).slice(0,12);
    results.innerHTML = hits.map(function(it){
      return '<a class="cmd-item" href="'+it.href+'"><strong>'+it.title.replace(/</g,'&lt;')+'</strong></a>';
    }).join('') || '<div class="cmd-empty">无结果</div>';
  }
  function openPal(){ pal.classList.add('open'); input.value=''; render(''); setTimeout(function(){ input.focus(); }, 10); }
  function closePal(){ pal.classList.remove('open'); }
  window.addEventListener('keydown', function(e){
    if ((e.metaKey||e.ctrlKey) && e.key.toLowerCase()==='k'){ e.preventDefault(); openPal(); }
    if (e.key==='Escape') closePal();
  });
  pal.addEventListener('click', function(e){ if(e.target===pal) closePal(); });
  input.addEventListener('input', function(){ render(input.value); });

  /* easter egg ai168 */
  var buf='';
  window.addEventListener('keypress', function(e){
    if (e.target && /input|textarea/i.test(e.target.tagName)) return;
    buf=(buf+e.key).slice(-5).toLowerCase();
    if (buf==='ai168'){
      buf='';
      showToast('AI168 粒子爆发');
      if (window.__brainAPI && window.__brainAPI.triggerShockwave) window.__brainAPI.triggerShockwave();
      document.body.classList.add('egg-burst');
      setTimeout(function(){ document.body.classList.remove('egg-burst'); }, 1200);
      // burst dots
      if (!reduced){
        for (var i=0;i<24;i++){
          var d=document.createElement('div'); d.className='burst-dot';
          d.style.left=(50+Math.cos(i)*10)+'%'; d.style.top=(40+Math.sin(i)*8)+'%';
          d.style.setProperty('--dx', (Math.cos(i/24*Math.PI*2)*120)+'px');
          d.style.setProperty('--dy', (Math.sin(i/24*Math.PI*2)*90)+'px');
          document.body.appendChild(d);
          setTimeout((function(el){ return function(){ el.remove(); }; })(d), 900);
        }
      }
    }
  });
})();
