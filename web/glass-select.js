// Liquid-glass pickers for the language and audience selects. The native <select> stays in the DOM as the
// source of truth — app.js and i18n.js read it and listen for `change` — this only replaces how it looks and
// how it is operated (pointer and keyboard).
(() => {
  let uid = 0;

  // Specular highlight that follows the pointer across a glass surface.
  function followSheen(surface) {
    surface.addEventListener('pointermove', e => {
      const r = surface.getBoundingClientRect();
      surface.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      surface.style.setProperty('--my', (e.clientY - r.top) + 'px');
    }, {passive: true});
  }

  function enhance(select) {
    const id = 'glass-' + (++uid);
    const label = select.closest('label');
    const wrap = document.createElement('div');
    wrap.className = 'glass-select'; wrap.dataset.for = select.id;
    wrap.innerHTML =
      `<span class="sr-only" id="${id}-name"></span>` +
      `<button type="button" class="glass-trigger" id="${id}-btn" aria-haspopup="listbox" aria-expanded="false" aria-controls="${id}-list">` +
      `<span class="glass-sheen" aria-hidden="true"></span><span class="glass-value" id="${id}-value"></span>` +
      `<svg class="glass-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="M3 4.5 6 7.5 9 4.5"/></svg></button>` +
      `<div class="glass-panel" id="${id}-list" role="listbox" tabindex="-1" hidden><span class="glass-sheen" aria-hidden="true"></span><span class="glass-blob" aria-hidden="true"></span></div>`;
    const button = wrap.querySelector('.glass-trigger'), panel = wrap.querySelector('.glass-panel');
    const blob = wrap.querySelector('.glass-blob'), value = wrap.querySelector('.glass-value'), name = wrap.querySelector('.sr-only');

    // Accessible name: the visible "Audience" caption when there is one (i18n translates it), else the select's aria-label.
    const caption = label && label.querySelector('span');
    if (caption) { caption.id ||= id + '-caption'; button.setAttribute('aria-labelledby', caption.id + ' ' + value.id); name.remove(); }
    else { name.textContent = select.getAttribute('aria-label') || ''; button.setAttribute('aria-labelledby', name.id + ' ' + value.id); }
    if (label) label.htmlFor = button.id;                    // clicking the caption opens the picker
    panel.setAttribute('aria-labelledby', button.getAttribute('aria-labelledby').split(' ')[0]);

    select.classList.add('glass-native'); select.tabIndex = -1; select.setAttribute('aria-hidden', 'true');
    select.after(wrap);

    let options = [], active = -1, isOpen = false, signature = '', hideTimer = 0;

    function build() {
      const next = [...select.options].map(o => o.value + '\u0000' + o.textContent).join('\u0001');
      if (next === signature) return sync();                 // i18n re-sets identical text; ignore to avoid loops
      signature = next;
      options.forEach(el => el.remove());
      options = [...select.options].map((o, i) => {
        const el = document.createElement('div');
        el.className = 'glass-option'; el.id = `${id}-o${i}`; el.setAttribute('role', 'option'); el.dataset.value = o.value;
        el.innerHTML = '<span></span><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 6.2 5 8.6 9.5 3.6"/></svg>';
        el.firstChild.textContent = o.textContent;
        el.addEventListener('pointermove', () => setActive(i));
        el.addEventListener('click', e => { e.preventDefault(); choose(i); });  // preventDefault: don't re-trigger the <label>
        panel.append(el);
        return el;
      });
      sync();
    }
    function sync() {
      options.forEach(el => el.setAttribute('aria-selected', String(el.dataset.value === select.value)));
      const text = select.selectedOptions[0] ? select.selectedOptions[0].textContent : '';
      if (value.textContent !== text) value.textContent = text;
    }
    const selectedIndex = () => Math.max(0, options.findIndex(el => el.dataset.value === select.value));

    function setActive(i, instant) {
      if (i < 0 || i >= options.length) return;
      if (active === i && !instant) return;
      options.forEach((el, j) => el.classList.toggle('active', j === i));
      active = i;
      panel.setAttribute('aria-activedescendant', options[i].id);
      const el = options[i];
      blob.classList.toggle('instant', !!instant);
      blob.style.height = el.offsetHeight + 'px';
      blob.style.transform = `translateY(${el.offsetTop}px)`;
      if (instant) void blob.offsetWidth;                    // commit the jump before re-enabling the spring
      blob.classList.remove('instant');
      el.scrollIntoView({block: 'nearest'});
    }

    function open() {
      if (isOpen) return;
      for (const other of document.querySelectorAll('.glass-select.open')) if (other !== wrap) other.dispatchEvent(new Event('glass-close'));
      isOpen = true; clearTimeout(hideTimer);
      panel.hidden = false; wrap.classList.add('open'); button.setAttribute('aria-expanded', 'true');
      active = -1; setActive(selectedIndex(), true);
      requestAnimationFrame(() => requestAnimationFrame(() => { if (isOpen) wrap.classList.add('shown'); }));
      panel.focus({preventScroll: true});
      document.addEventListener('pointerdown', outside, true);
    }
    function close(returnFocus) {
      if (!isOpen) return;
      isOpen = false;
      wrap.classList.remove('shown'); button.setAttribute('aria-expanded', 'false');
      document.removeEventListener('pointerdown', outside, true);
      hideTimer = setTimeout(() => { if (!isOpen) { panel.hidden = true; wrap.classList.remove('open'); } }, 260);
      if (returnFocus) button.focus();
    }
    function choose(i) {
      const v = options[i].dataset.value;
      close(true);
      if (select.value === v) return;
      select.value = v; sync();
      select.dispatchEvent(new Event('change', {bubbles: true}));
    }
    const outside = e => { if (!wrap.contains(e.target) && !(label && label.contains(e.target))) close(false); };

    button.addEventListener('click', e => { e.preventDefault(); isOpen ? close(true) : open(); });
    button.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); open(); }
    });
    panel.addEventListener('keydown', e => {
      const last = options.length - 1;
      const moves = {ArrowDown: Math.min(last, active + 1), ArrowUp: Math.max(0, active - 1), Home: 0, End: last};
      if (e.key in moves) { e.preventDefault(); setActive(moves[e.key]); }
      else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(active); }
      else if (e.key === 'Escape') { e.preventDefault(); close(true); }
      else if (e.key === 'Tab') close(false);
    });
    panel.addEventListener('click', e => e.preventDefault());
    wrap.addEventListener('glass-close', () => close(false));

    followSheen(button); followSheen(panel);

    select.addEventListener('change', sync);
    // i18n.js rewrites option text when the language changes; mirror it.
    new MutationObserver(build).observe(select, {subtree: true, childList: true, characterData: true});
    build();
  }

  for (const pill of document.querySelectorAll('.coverage-trigger')) followSheen(pill);
  for (const id of ['language', 'audience-role']) {
    const select = document.getElementById(id);
    if (select) enhance(select);
  }
})();
