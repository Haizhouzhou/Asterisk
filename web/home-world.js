// Home background: a solid world map that lights up around the pointer and stays dim elsewhere.
// Two layers are pre-rendered once per resize — a dim silhouette and a lit map with country borders —
// and each frame reveals the lit layer through a soft radial mask centred on the pointer.
(() => {
  const data = window.WORLD_MAP;
  const canvas = document.getElementById('home-world');
  if (!data || !canvas) return;
  const ctx = canvas.getContext('2d');
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const land = new Path2D(data.land), borders = new Path2D(data.borders);

  let width = 0, height = 0, dpr = 1, radius = 0;
  let dim = null, lit = null, spot = null, spotCtx = null;
  const target = {x: 0, y: 0, on: 0}, glow = {x: 0, y: 0, on: 0};
  let frame = 0;

  const isHome = () => document.body.classList.contains('is-home');
  const layer = () => { const c = document.createElement('canvas'); c.width = canvas.width; c.height = canvas.height; return c; };

  function layout() {
    const css = getComputedStyle(document.documentElement);
    const ink = css.getPropertyValue('--ink').trim() || '#243746', brand = css.getPropertyValue('--brand').trim() || '#293fdf';
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = innerWidth; height = innerHeight;
    canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
    // Fill the width on desktop; on tall narrow screens keep the map large enough to read and crop the sides.
    const scale = Math.max(width / data.width, height * 0.55 / data.height);
    const ox = (width - data.width * scale) / 2, oy = Math.max(height * 0.08, (height - data.height * scale) / 2);
    radius = Math.max(120, Math.min(210, width * 0.14));
    const px = 1 / scale;                                   // one CSS pixel in map units
    const paint = (c, draw) => {
      const g = c.getContext('2d');
      g.setTransform(dpr * scale, 0, 0, dpr * scale, dpr * ox, dpr * oy);
      g.lineJoin = 'round'; g.lineCap = 'round';
      draw(g);
    };
    dim = layer(); lit = layer(); spot = layer(); spotCtx = spot.getContext('2d');
    paint(dim, g => {
      g.fillStyle = ink; g.globalAlpha = 0.07; g.fill(land, 'evenodd');
      g.strokeStyle = ink; g.globalAlpha = 0.1; g.lineWidth = 0.6 * px; g.stroke(land);
    });
    paint(lit, g => {
      g.fillStyle = brand; g.globalAlpha = 0.55; g.fill(land, 'evenodd');
      g.globalAlpha = 1; g.strokeStyle = 'rgba(255,255,255,.85)'; g.lineWidth = 0.7 * px; g.stroke(borders);
      g.strokeStyle = brand; g.lineWidth = 0.9 * px; g.stroke(land);
    });
    draw();
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (dim) ctx.drawImage(dim, 0, 0);
    if (glow.on < 0.01 || !lit) return;
    // Only touch the square around the pointer: mask it with a radial gradient, then keep the lit map inside it.
    const r = radius * dpr, cx = glow.x * dpr, cy = glow.y * dpr;
    const x0 = Math.max(0, Math.floor(cx - r)), y0 = Math.max(0, Math.floor(cy - r));
    const w = Math.min(canvas.width, Math.ceil(cx + r)) - x0, h = Math.min(canvas.height, Math.ceil(cy + r)) - y0;
    if (w <= 0 || h <= 0) return;
    const g = spotCtx.createRadialGradient(cx, cy, 0, cx, cy, r);
    for (let i = 0; i <= 8; i++) { const d = i / 8, t = 1 - d * d * (3 - 2 * d); g.addColorStop(d, `rgba(0,0,0,${t * glow.on})`); }
    spotCtx.globalCompositeOperation = 'copy';
    spotCtx.fillStyle = g; spotCtx.fillRect(x0, y0, w, h);
    spotCtx.globalCompositeOperation = 'source-in';
    spotCtx.drawImage(lit, x0, y0, w, h, x0, y0, w, h);
    ctx.drawImage(spot, x0, y0, w, h, x0, y0, w, h);
  }

  function tick() {
    frame = 0;
    const k = reduceMotion ? 1 : 0.2;
    if (glow.on < 0.01 && target.on) { glow.x = target.x; glow.y = target.y; }  // appear where the pointer is, not slide in
    glow.x += (target.x - glow.x) * k; glow.y += (target.y - glow.y) * k; glow.on += (target.on - glow.on) * (reduceMotion ? 1 : 0.12);
    draw();
    const moving = Math.abs(target.x - glow.x) > 0.3 || Math.abs(target.y - glow.y) > 0.3 || Math.abs(target.on - glow.on) > 0.01;
    if (moving) schedule(); else if (!target.on) { glow.on = 0; draw(); }
  }
  const schedule = () => { if (!frame && isHome()) frame = requestAnimationFrame(tick); };

  addEventListener('pointermove', e => { target.x = e.clientX; target.y = e.clientY; target.on = 1; schedule(); }, {passive: true});
  document.documentElement.addEventListener('pointerleave', () => { target.on = 0; schedule(); });
  addEventListener('blur', () => { target.on = 0; schedule(); });
  let resizeTimer = 0;
  addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(layout, 80); });
  // The home view is toggled by a body class; redraw when it comes back so the canvas never shows a stale size.
  new MutationObserver(() => { if (isHome() && (width !== innerWidth || height !== innerHeight)) layout(); }).observe(document.body, {attributes: true, attributeFilter: ['class']});
  layout();
})();
