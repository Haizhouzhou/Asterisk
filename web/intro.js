// First-visit intro: the real home logo is lifted above a cream overlay with two role cards. Choosing one sets the
// audience picker, flies the card into that picker (top right), settles the logo back into the home page and
// fades the search page in. Loaded without defer so the <html class="intro-on"> flag is set before first paint;
// the rest waits for DOMContentLoaded, i.e. until the deferred scripts (i18n, glass pickers, app) have run.
document.documentElement.classList.toggle('intro-on', !location.hash);
document.addEventListener('DOMContentLoaded', () => {
  const root = document.documentElement, intro = document.getElementById('intro');
  if (!intro) return;
  if (!root.classList.contains('intro-on') || !document.body.classList.contains('is-home')) { root.classList.remove('intro-on'); intro.remove(); return; }

  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const ease = 'cubic-bezier(.65,0,.35,1)', settle = 'cubic-bezier(.22,1,.36,1)';
  const mark = document.querySelector('.home-mark'), body = intro.querySelector('.intro-body');
  const select = document.getElementById('audience-role');
  // Keep focus inside the intro: the page underneath (except the language picker) is inert until a role is chosen.
  const locked = [document.querySelector('main'), document.getElementById('brand-home'), document.getElementById('coverage-open'), document.querySelector('.role')].filter(Boolean);
  locked.forEach(el => { el.inert = true; });
  let busy = false;

  // Centre the logo above the role cards, scaled up; the same element later animates back to transform:none.
  function place() {
    mark.style.transform = 'none';
    const r = mark.getBoundingClientRect(), b = body.getBoundingClientRect();
    const scale = Math.min(1.5, (innerWidth - 48) / r.width);
    const cy = Math.max(r.height * scale / 2 + 24, b.top - 44 - r.height * scale / 2);
    mark.style.transform = `translate(${innerWidth / 2 - (r.left + r.width / 2)}px, ${cy - (r.top + r.height / 2)}px) scale(${scale})`;
  }
  place();
  addEventListener('resize', onResize);
  function onResize() { if (!busy) place(); }
  requestAnimationFrame(() => {
    root.classList.add('intro-ready');
    intro.querySelector('.intro-role').focus({preventScroll: true});
  });

  for (const card of intro.querySelectorAll('.intro-role')) {
    card.addEventListener('click', () => choose(card));
    card.addEventListener('pointermove', e => {
      const r = card.getBoundingClientRect();
      card.style.setProperty('--mx', (e.clientX - r.left) + 'px'); card.style.setProperty('--my', (e.clientY - r.top) + 'px');
    }, {passive: true});
  }

  function choose(card) {
    if (busy) return;
    busy = true;
    removeEventListener('resize', onResize);
    if (select && select.value !== card.dataset.audience) {
      select.value = card.dataset.audience;
      select.dispatchEvent(new Event('change', {bubbles: true}));  // glass-select.js and app.js both listen
    }
    const trigger = document.querySelector('.glass-select[data-for=audience-role] .glass-trigger');
    const from = card.getBoundingClientRect(), to = trigger ? trigger.getBoundingClientRect() : null;
    const flies = !reduceMotion && to && to.width > 0;

    // The overlay stays visible on its own class while the page-wide intro flags come off.
    intro.classList.add('leaving');
    mark.style.position = 'relative'; mark.style.zIndex = '1002';
    root.classList.remove('intro-on', 'intro-ready');
    locked.forEach(el => { el.inert = false; });

    // 1. The chosen card becomes a glass pill and flies into the audience picker; the others fade away.
    const others = [...intro.querySelectorAll('.intro-title, .intro-note, .intro-role')].filter(el => el !== card);
    others.forEach(el => el.animate([{opacity: 1}, {opacity: 0, transform: 'scale(.96)'}], {duration: 220, easing: 'ease-out', fill: 'forwards'}));
    let ghost = null;
    if (flies) {
      ghost = document.createElement('div');
      ghost.className = 'intro-ghost';
      ghost.innerHTML = '<div class="intro-ghost-inner"></div>';
      ghost.firstChild.innerHTML = card.innerHTML;
      Object.assign(ghost.style, {left: from.left + 'px', top: from.top + 'px', width: from.width + 'px', height: from.height + 'px'});
      document.body.append(ghost);
      card.style.visibility = 'hidden';
      ghost.firstChild.animate([{opacity: 1}, {opacity: 0}], {duration: 200, easing: 'ease-out', fill: 'forwards'});
      ghost.animate([
        {left: from.left + 'px', top: from.top + 'px', width: from.width + 'px', height: from.height + 'px', borderRadius: '22px'},
        {left: to.left + 'px', top: to.top + 'px', width: to.width + 'px', height: to.height + 'px', borderRadius: '999px'}
      ], {duration: 820, easing: ease, fill: 'forwards'});
      ghost.animate([{opacity: 1}, {opacity: 0}], {duration: 260, delay: 820, fill: 'forwards'});
    } else {
      card.animate([{opacity: 1}, {opacity: 0}], {duration: 220, fill: 'forwards'});
    }

    // 2. The logo glides back into the home page.
    const markMove = mark.animate([{transform: mark.style.transform}, {transform: 'none'}], {duration: reduceMotion ? 1 : 950, easing: settle, fill: 'forwards'});
    mark.style.transform = '';

    // 3. The overlay dissolves and the search page comes in piece by piece.
    intro.animate([{opacity: 1}, {opacity: 0}], {duration: 520, delay: reduceMotion ? 0 : 380, easing: 'ease-out', fill: 'forwards'});
    const pieces = [...document.querySelectorAll('.home-tag, .home-form, .home-try, .home-foot, .masthead .header-right > :not(.glass-select[data-for=language])')];
    pieces.forEach((el, i) => el.animate(
      [{opacity: 0, transform: 'translateY(14px)'}, {opacity: 1, transform: 'none'}],
      {duration: reduceMotion ? 1 : 650, delay: reduceMotion ? 0 : 620 + i * 90, easing: settle, fill: 'backwards'}));

    const done = Math.max(1150, 620 + pieces.length * 90 + 650);
    setTimeout(() => {
      markMove.cancel(); mark.style.position = mark.style.zIndex = '';
      intro.remove(); if (ghost) ghost.remove();
      const search = document.getElementById('home-search');
      if (search && document.body.classList.contains('is-home')) search.focus({preventScroll: true});
    }, reduceMotion ? 300 : done);
  }
});
