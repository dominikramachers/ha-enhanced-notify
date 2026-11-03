// Enhanced Notify: Glocke (Sidebar, Bell-Karte, optional Kiosk-/Handy-Header), Meldungsliste, Admin-Karte (Push je Typ und Person).
// Wird von der Integration enhanced_notify selbst ausgeliefert und in HA geladen (Websocket enhanced_notify/subscribe|mark_read|delete|set_type).
// Mehrfaches Laden ist unkritisch: die erste geladene Kopie gewinnt.
(() => {
if (window.__enhancedNotifyLoaded) return;
window.__enhancedNotifyLoaded = 1;
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
// Icon-Angabe: Bild (Pfad auf diese HA-Instanz, http(s)-Adresse, data:image) oder Icon-Name (mdi:...)
const isImg = (s) => typeof s === 'string' && (/^\/(?!\/)\S/.test(s) || /^https?:\/\/\S/i.test(s) || /^data:image\/(png|jpe?g|gif|webp|svg\+xml);base64,/i.test(s));
const iconHtml = (s) => (isImg(s) ? `<img src="${esc(s)}" alt="" draggable="false">` : `<ha-icon icon="${esc(s)}"></ha-icon>`);
const def = (n, c) => { if (!customElements.get(n)) customElements.define(n, c); };
window.customCards = window.customCards || [];
const reg = (t, n, d) => { if (!window.customCards.some((c) => c.type === t)) window.customCards.push({ type: t, name: n, description: d }); };
const navigate = (path) => { history.pushState(null, '', path); window.dispatchEvent(new CustomEvent('location-changed', { bubbles: true, composed: true })); };

// ---------- Datenquelle (gemeinsam für alle Komponenten) ----------
const N = (window.enhancedNotify = { snap: null, hass: null, started: false, retry: 0, ls: new Set(), bells: new Set(), filter: 'all' });
N.setHass = (h) => {
  if (!h) return;
  N.hass = h;
  if (N.started || !h.connection || Date.now() < N.retry) return;
  N.started = true;
  h.connection.subscribeMessage((s) => { N.snap = s; N.emit(); }, { type: 'enhanced_notify/subscribe' })
    .catch(() => { N.started = false; N.retry = Date.now() + 30000; });
};
// hass auch ohne Karte beziehen (Sidebar-Glocke funktioniert damit auf jeder HA-Seite)
N.autoHass = () => {
  if (N.started) return;
  const ha = document.querySelector('home-assistant');
  if (ha && ha.hass) N.setHass(ha.hass);
};
N.emit = () => {
  N.bells.forEach((b) => { if (b.isConnected) N.paint(b); else N.bells.delete(b); });
  try { N.sidebar(); } catch (e) { /* ignore */ }
  N.ls.forEach((f) => { try { f(N.snap); } catch (e) { console.error('enhanced-notify', e); } });
};
N.call = (msg) => N.hass.callWS(msg);
N.read = (ids, read = true) => N.call({ type: 'enhanced_notify/mark_read', ids, read });
N.readAll = () => N.call({ type: 'enhanced_notify/mark_read', all: true });
N.del = (ids) => N.call({ type: 'enhanced_notify/delete', ids });
N.delRead = () => N.call({ type: 'enhanced_notify/delete', all: true, only_read: true });
const items = () => (N.snap && N.snap.items) || [];
const unread = () => (N.snap ? N.snap.unread || 0 : 0);

const day0 = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
const hm = (d) => d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
const when = (iso) => {
  const d = new Date(iso), now = new Date(), diff = (now - d) / 60000;
  if (diff < 1) return 'Gerade eben';
  if (diff < 60) return `vor ${Math.floor(diff)} Min.`;
  const dd = Math.round((day0(now) - day0(d)) / 864e5);
  if (dd === 0) return `Heute, ${hm(d)}`;
  if (dd === 1) return `Gestern, ${hm(d)}`;
  return `${d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })}, ${hm(d)}`;
};
const groupOf = (iso) => { const dd = Math.round((day0(new Date()) - day0(new Date(iso))) / 864e5); return dd <= 0 ? 'Heute' : dd === 1 ? 'Gestern' : 'Früher'; };
const cat = (id) => ((N.snap && N.snap.categories) || {})[id] || { name: 'System', icon: 'mdi:cog-outline', color: '#6B7280' };

// ---------- Glocke ----------
const BELL_CSS = `
.nbell{position:relative;flex:none;display:flex;align-items:center;justify-content:center;padding:0;margin:0;border:0;cursor:pointer;color:var(--primary-text-color,#101B2D);-webkit-tap-highlight-color:transparent;touch-action:manipulation;transition:transform .15s}
.nbell:active{transform:scale(.93)}
.nbell.k{width:clamp(30px,4.6vh,42px);height:clamp(30px,4.6vh,42px);border-radius:50%;background:var(--k-card,var(--card-background-color,#1B273A));border:1px solid var(--k-border,var(--dl-line,rgba(255,255,255,.08)));--mdc-icon-size:clamp(17px,2.8vh,24px)}
.nbell.m{width:48px;height:48px;border-radius:50%;background:var(--card-background-color,#fff);box-shadow:var(--dl-shadow,0 3px 12px rgba(17,24,39,.08));--mdc-icon-size:22px}
.nbell .nb{position:absolute;top:-5px;right:-5px;min-width:19px;height:19px;padding:0 5px;border-radius:10px;background:var(--dl-red,#EF4444);color:#fff;font:700 11px/19px Roboto,'Segoe UI',sans-serif;font-style:normal;text-align:center;box-shadow:0 0 0 2px var(--k-card,var(--card-background-color,#fff))}
.nbell .nb[hidden]{display:none}
.nbell.has ha-icon{color:var(--dl-amber-text,#F59E0B)}
.nbell.ring ha-icon{animation:nbring 1.1s ease-in-out;transform-origin:50% 12%}
@keyframes nbring{0%,100%{transform:rotate(0)}12%{transform:rotate(-16deg)}24%{transform:rotate(13deg)}36%{transform:rotate(-9deg)}48%{transform:rotate(6deg)}60%{transform:rotate(0)}}`;
const ensureStyle = (sr) => {
  if (sr.querySelector('style.nbs')) return;
  const st = document.createElement('style'); st.className = 'nbs'; st.textContent = BELL_CSS; sr.appendChild(st);
};
N.paint = (b) => {
  const n = unread();
  const nb = b.querySelector('.nb'), ic = b.querySelector('ha-icon');
  nb.hidden = n === 0; nb.textContent = n > 99 ? '99+' : String(n);
  ic.setAttribute('icon', n ? 'mdi:bell-ring-outline' : 'mdi:bell-outline');
  b.classList.toggle('has', n > 0);
  b.setAttribute('aria-label', n ? `Benachrichtigungen, ${n} ungelesen` : 'Benachrichtigungen');
  if (b._n !== undefined && n > b._n) { b.classList.remove('ring'); void b.offsetWidth; b.classList.add('ring'); }
  b._n = n;
};
const bellEl = (variant) => {
  const b = document.createElement('button');
  b.className = `nbell ${variant}`;
  b.innerHTML = '<ha-icon icon="mdi:bell-outline"></ha-icon><i class="nb" hidden></i>';
  b.addEventListener('click', (e) => { e.stopPropagation(); N.open(); });
  N.bells.add(b);
  N.paint(b);
  return b;
};
const kioskBell = (host) => {
  const sr = host.shadowRoot; if (!sr || sr.querySelector('.nbell')) return;
  const dr = sr.querySelector('.dr'); if (!dr) return;
  ensureStyle(sr); dr.appendChild(bellEl('k'));
};
const mobileBell = (host) => {
  const sr = host.shadowRoot; if (!sr || sr.querySelector('.nbell')) return;
  const sb = sr.querySelector('.sb'); if (!sb || !sb.parentNode) return;
  ensureStyle(sr);
  const w = document.createElement('div'); w.style.cssText = 'display:flex;gap:10px;flex:none';
  sb.parentNode.insertBefore(w, sb); w.appendChild(bellEl('m')); w.appendChild(sb);
};
// Glocke als eigenständige Karte für beliebige Dashboards: type: custom:enhanced-notify-bell
class EnhancedNotifyBell extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: 'open' }); }
  setConfig(c) { this._c = c || {}; this._build(); }
  getCardSize() { return 1; }
  getGridOptions() { return { columns: 3, rows: 1, min_columns: 2, min_rows: 1 }; }
  set hass(h) { N.setHass(h); }
  connectedCallback() { this._build(); }
  _build() {
    const sr = this.shadowRoot; if (!sr) return;
    if (!sr.querySelector('.nbell')) {
      ensureStyle(sr);
      const st = document.createElement('style'); st.textContent = ':host{display:flex;justify-content:center;padding:6px}'; sr.appendChild(st);
      sr.appendChild(bellEl('m'));
    }
    N.paint(sr.querySelector('.nbell'));
  }
}
def('enhanced-notify-bell', EnhancedNotifyBell);
def('doralab-notify-bell', class extends EnhancedNotifyBell {}); // alter Kartenname (bis 0.3.x), entfällt in 2.0
reg('enhanced-notify-bell', 'Benachrichtigungen (Glocke)', 'Glocke mit Zähler, öffnet die Meldungsliste');

// Optionale Anbindung an die DORALAB-Dashboards (nur aktiv, wenn es diese Elemente gibt)
customElements.whenDefined('doralab-kt-page').then((K) => {
  const P = K.prototype; if (P.__nb) return; P.__nb = 1;
  const ou = P._upd;
  P._upd = function () { const r = ou.apply(this, arguments); try { N.setHass(this._hass); kioskBell(this); } catch (e) { console.error('enhanced-notify kiosk', e); } return r; };
});
customElements.whenDefined('doralab-home-header').then((C) => {
  const P = C.prototype; if (P.__nb) return; P.__nb = 1;
  const ou = P._update;
  P._update = function () { const r = ou.apply(this, arguments); try { N.setHass(this._h); mobileBell(this); } catch (e) { console.error('enhanced-notify mobile', e); } return r; };
});

// ---------- Glocke der HA-Sidebar übernehmen (Web und App) ----------
// Die Standard-Glocke von HA öffnet statt der leeren HA-Schublade unsere Liste und zeigt unseren Zähler.
const SB_CSS = '#sidebar-notifications .badge:not([data-nb]){display:none!important}';
const haSidebar = () => {
  const ha = document.querySelector('home-assistant');
  const m = ha && ha.shadowRoot && ha.shadowRoot.querySelector('home-assistant-main');
  return (m && m.shadowRoot && m.shadowRoot.querySelector('ha-sidebar')) || null;
};
N.sidebar = () => {
  N.autoHass();
  const sb = haSidebar(); if (!sb || !sb.shadowRoot) return;
  const item = sb.shadowRoot.getElementById('sidebar-notifications') || sb.shadowRoot.querySelector('.notifications');
  if (!item) return;
  if (!sb.shadowRoot.querySelector('style.nbs2')) {
    const st = document.createElement('style'); st.className = 'nbs2'; st.textContent = SB_CSS; sb.shadowRoot.appendChild(st);
  }
  if (!item._nbHooked) {
    item._nbHooked = true;
    item.addEventListener('click', (e) => {
      e.stopImmediatePropagation(); e.preventDefault();
      N.open();
      if (window.matchMedia('(max-width:870px)').matches) sb.dispatchEvent(new CustomEvent('hass-toggle-menu', { bubbles: true, composed: true, detail: { open: false } }));
    }, true);
  }
  const n = unread(), ic = item.querySelector('ha-svg-icon');
  ['start', 'end'].forEach((slot) => {
    let b = item.querySelector(`.badge[data-nb][slot="${slot}"]`);
    if (!n) { if (b) b.remove(); return; }
    if (!b) {
      b = document.createElement('span'); b.className = 'badge'; b.dataset.nb = '1'; b.setAttribute('slot', slot);
      if (slot === 'start' && ic) ic.after(b); else item.appendChild(b);
    }
    const t = n > 99 ? '99+' : String(n); if (b.textContent !== t) b.textContent = t;
  });
};
setTimeout(() => { try { N.sidebar(); } catch (e) { /* ignore */ } }, 1500);
setInterval(() => { try { N.sidebar(); } catch (e) { /* ignore */ } }, 3000);

// ---------- Meldungsliste (Popup) ----------
const PCSS = `
*{box-sizing:border-box}
button{font:inherit;color:inherit;border:0;padding:0;margin:0;background:none;cursor:pointer;-webkit-tap-highlight-color:transparent;touch-action:manipulation}
:host{position:fixed;inset:0;z-index:2500;display:none;font-family:var(--paper-font-body1_-_font-family,Roboto,'Segoe UI',sans-serif)}
:host(.open){display:block}
.ov{position:absolute;inset:0;background:rgba(3,6,14,.62);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:18px;animation:fin .25s ease}
@keyframes fin{from{opacity:0}to{opacity:1}}
@keyframes pop{from{opacity:0;transform:translateY(14px) scale(.97)}to{opacity:1;transform:none}}
.sh{width:min(660px,100%);height:min(86vh,800px);display:flex;flex-direction:column;overflow:hidden;border-radius:26px;background:var(--dl-popup-bg,var(--card-background-color,#1B273A));color:var(--primary-text-color,#F1F5F9);border:1px solid var(--dl-line,rgba(127,127,127,.2));box-shadow:0 30px 90px rgba(0,0,0,.5);color-scheme:var(--dl-color-scheme,dark);animation:pop .3s cubic-bezier(.2,.9,.3,1.05)}
.hd{flex:none;display:flex;align-items:center;gap:8px;padding:18px 14px 8px 22px}
.hd .tt{flex:1;min-width:0}
.hd h2{margin:0;font-size:22px;font-weight:800;letter-spacing:-.01em}
.hd small{display:block;margin-top:2px;font-size:13px;color:var(--secondary-text-color,#94A3B8)}
.ib{flex:none;width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:var(--secondary-text-color,#94A3B8);--mdc-icon-size:23px;transition:background .15s}
.ib:active,.ib:hover{background:var(--dl-chip-bg,rgba(127,127,127,.14))}
.ib[disabled]{opacity:.35;pointer-events:none}
.fl{flex:none;display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;padding:6px 22px 12px}
.fl::-webkit-scrollbar{display:none}
.cp{flex:none;height:34px;padding:0 14px;border-radius:17px;display:flex;align-items:center;gap:7px;font-size:13px;font-weight:700;white-space:nowrap;background:var(--dl-chip-bg,rgba(127,127,127,.14));color:var(--secondary-text-color,#94A3B8);--mdc-icon-size:16px}
.cp.on{background:var(--primary-text-color,#F1F5F9);color:var(--dl-popup-bg,var(--card-background-color,#1B273A))}
.cp i{font-style:normal;font-size:11px;font-weight:800;min-width:18px;height:18px;border-radius:9px;padding:0 5px;line-height:18px;text-align:center;background:var(--dl-red,#EF4444);color:#fff}
.ls{flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch;padding:0 14px calc(18px + env(safe-area-inset-bottom,0px))}
.gh{margin:12px 8px 6px;font-size:11.5px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--secondary-text-color,#94A3B8)}
.it{position:relative;display:flex;align-items:center;gap:12px;padding:10px 6px 10px 12px;margin-bottom:8px;border-radius:18px;background:var(--secondary-background-color,rgba(127,127,127,.1));cursor:pointer;transition:background .2s}
.it.un{background:var(--dl-blue-soft,rgba(96,165,250,.16))}
.it.un::before{content:'';position:absolute;left:5px;top:50%;width:6px;height:6px;margin-top:-3px;border-radius:50%;background:var(--dl-blue,#60A5FA)}
.ic{flex:none;width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--c) 22%,transparent);color:var(--c);--mdc-icon-size:23px;margin-left:4px;overflow:hidden}
.ic img{width:100%;height:100%;object-fit:cover;display:block}
.tx{flex:1;min-width:0}
.t1{display:flex;align-items:baseline;gap:8px}
.t1 b{font-size:15px;font-weight:700;line-height:1.25;min-width:0;overflow:hidden;text-overflow:ellipsis}
.it:not(.un) .t1 b{font-weight:600;opacity:.85}
.cn{flex:none;font-style:normal;font-size:11px;font-weight:800;padding:1px 7px;border-radius:9px;background:var(--dl-chip-bg,rgba(127,127,127,.2));color:var(--secondary-text-color,#94A3B8)}
.t2{margin-top:3px;font-size:14px;line-height:1.35;white-space:pre-line;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;color:var(--primary-text-color,#F1F5F9);opacity:.92}
.it:not(.un) .t2{opacity:.7}
.t3{margin-top:5px;font-size:12px;color:var(--secondary-text-color,#94A3B8)}
.ac{flex:none;display:flex;flex-direction:column;gap:2px}
.ac .ib{width:34px;height:34px;--mdc-icon-size:19px}
.em{display:flex;flex-direction:column;align-items:center;gap:10px;padding:64px 20px;text-align:center;color:var(--secondary-text-color,#94A3B8);--mdc-icon-size:54px}
.em b{font-size:16px;color:var(--primary-text-color,#F1F5F9)}
.em span{font-size:13px}
@media (max-width:640px){
.ov{padding:0;align-items:flex-end}
.sh{width:100%;height:calc(100% - env(safe-area-inset-top,0px) - 14px);border-radius:24px 24px 0 0}
.hd{padding-top:16px}
}`;
class EnhancedNotifyPanel extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: 'open' }); this._open = false; }
  connectedCallback() {
    this._f = () => this._render();
    N.ls.add(this._f);
  }
  disconnectedCallback() { N.ls.delete(this._f); }
  open() {
    this._open = true; this.classList.add('open');
    this._render(true);
    this._key = (e) => { if (e.key === 'Escape') this.close(); };
    document.addEventListener('keydown', this._key);
  }
  close() {
    this._open = false; this.classList.remove('open');
    if (this._key) { document.removeEventListener('keydown', this._key); this._key = null; }
  }
  _render(full) {
    if (!this._open) return;
    const sr = this.shadowRoot, list = items(), n = unread();
    if (full || !sr.querySelector('.sh')) {
      sr.innerHTML = `<style>${PCSS}</style><div class="ov"><div class="sh" role="dialog" aria-label="Benachrichtigungen"><div class="hd"><div class="tt"><h2>Benachrichtigungen</h2><small class="sm"></small></div><button class="ib" data-a="readall" aria-label="Alle als gelesen markieren"><ha-icon icon="mdi:check-all"></ha-icon></button><button class="ib" data-a="delread" aria-label="Gelesene löschen"><ha-icon icon="mdi:delete-sweep-outline"></ha-icon></button><button class="ib" data-a="close" aria-label="Schließen"><ha-icon icon="mdi:close"></ha-icon></button></div><div class="fl"></div><div class="ls"></div></div></div>`;
      sr.querySelector('.ov').addEventListener('click', (e) => { if (e.target.classList.contains('ov')) this.close(); });
      sr.querySelector('.sh').addEventListener('click', (e) => this._click(e));
    }
    const q = (s) => sr.querySelector(s);
    q('.sm').textContent = n ? `${n} ungelesen` : list.length ? 'Alles gelesen' : 'Keine Meldungen';
    q('[data-a="readall"]').disabled = n === 0;
    q('[data-a="delread"]').disabled = !list.some((i) => i.read);
    // Filter
    const counts = {}, ucounts = {};
    list.forEach((i) => { counts[i.category] = (counts[i.category] || 0) + 1; if (!i.read) ucounts[i.category] = (ucounts[i.category] || 0) + 1; });
    if (N.filter !== 'all' && N.filter !== 'unread' && !counts[N.filter]) N.filter = 'all';
    const order = Object.keys((N.snap && N.snap.categories) || {}).filter((k) => counts[k]);
    const chip = (id, name, icon, un) => `<button class="cp${N.filter === id ? ' on' : ''}" data-f="${esc(id)}">${icon ? `<ha-icon icon="${esc(icon)}"></ha-icon>` : ''}${esc(name)}${un ? `<i>${un}</i>` : ''}</button>`;
    const showFl = list.length > 0 && (order.length > 1 || (n > 0 && n < list.length) || N.filter === 'unread');
    const fl = showFl ? chip('all', 'Alle', '', 0) + chip('unread', 'Ungelesen', 'mdi:email-fast-outline', n) + order.map((k) => chip(k, cat(k).name, cat(k).icon, ucounts[k])).join('') : '';
    const flEl = q('.fl'); if (flEl.dataset.h !== fl) { flEl.dataset.h = fl; flEl.innerHTML = fl; }
    flEl.style.display = fl ? 'flex' : 'none';
    // Liste
    const shown = list.filter((i) => N.filter === 'all' || (N.filter === 'unread' ? !i.read : i.category === N.filter));
    const types = (N.snap && N.snap.types) || {};
    let html = '', last = '';
    shown.forEach((i) => {
      const g = groupOf(i.updated); if (g !== last) { last = g; html += `<div class="gh">${g}</div>`; }
      const c = cat(i.category), icon = i.icon || (types[i.type] && types[i.type].icon) || c.icon;
      html += `<div class="it${i.read ? '' : ' un'}" data-id="${esc(i.id)}" data-l="${esc(i.link || '')}" data-r="${i.read ? 1 : 0}"><span class="ic" style="--c:${esc(c.color)}">${iconHtml(icon)}</span><div class="tx"><div class="t1"><b>${esc(i.title)}</b>${i.count > 1 ? `<i class="cn">×${i.count}</i>` : ''}</div><div class="t2">${esc(i.message)}</div><div class="t3">${esc(c.name)} · ${esc(when(i.updated))}</div></div><div class="ac"><button class="ib" data-a="toggle" aria-label="${i.read ? 'Als ungelesen markieren' : 'Als gelesen markieren'}"><ha-icon icon="${i.read ? 'mdi:email-outline' : 'mdi:email-open-outline'}"></ha-icon></button><button class="ib" data-a="del" aria-label="Löschen"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button></div></div>`;
    });
    if (!html) html = `<div class="em"><ha-icon icon="mdi:bell-sleep-outline"></ha-icon><b>Alles ruhig</b><span>${N.snap ? (N.filter === 'unread' ? 'Alles gelesen' : 'Keine Benachrichtigungen') : 'Verbindung zur Benachrichtigungszentrale wird aufgebaut …'}</span></div>`;
    const ls = q('.ls'); if (ls.dataset.h === html) return;
    const top = ls.scrollTop; ls.dataset.h = html; ls.innerHTML = html; ls.scrollTop = top;
  }
  async _click(e) {
    const f = e.target.closest('[data-f]');
    if (f) { N.filter = f.dataset.f; this._render(); return; }
    const a = e.target.closest('[data-a]');
    const row = e.target.closest('.it');
    try {
      if (a && a.dataset.a === 'close') return this.close();
      if (a && a.dataset.a === 'readall') return await N.readAll();
      if (a && a.dataset.a === 'delread') return await N.delRead();
      if (a && row && a.dataset.a === 'toggle') return await N.read([row.dataset.id], row.dataset.r !== '1');
      if (a && row && a.dataset.a === 'del') return await N.del([row.dataset.id]);
      if (row) {
        if (row.dataset.r !== '1') await N.read([row.dataset.id]);
        if (row.dataset.l) { this.close(); navigate(row.dataset.l); }
      }
    } catch (err) { console.error('enhanced-notify', err); }
  }
}
def('enhanced-notify-panel', EnhancedNotifyPanel);
N.open = () => {
  N.autoHass();
  let p = document.querySelector('enhanced-notify-panel');
  if (!p) { p = document.createElement('enhanced-notify-panel'); document.body.appendChild(p); }
  p.open();
};

// ---------- Admin-Karte: Push je Meldungstyp und Person ----------
const ACSS = `
*{box-sizing:border-box}
button{font:inherit;color:inherit;border:0;padding:0;margin:0;background:none;cursor:pointer;-webkit-tap-highlight-color:transparent;touch-action:manipulation}
:host{display:block;font-family:var(--paper-font-body1_-_font-family,Roboto,'Segoe UI',sans-serif);color:var(--primary-text-color,#101B2D)}
.w{max-width:1100px;margin:0 auto;padding:6px 4px 40px}
h1{margin:6px 0 4px;font-size:26px;font-weight:800;letter-spacing:-.01em}
.lead{margin:0 0 16px;font-size:14px;line-height:1.45;color:var(--secondary-text-color,#667085)}
.pp{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:8px}
.pc{display:flex;align-items:center;gap:10px;padding:8px 16px 8px 8px;border-radius:999px;background:var(--card-background-color,#fff);box-shadow:var(--dl-shadow,0 3px 12px rgba(17,24,39,.08))}
.pa{position:relative;flex:none;width:40px;height:40px;border-radius:50%;background:var(--dl-chip-bg,rgba(127,127,127,.14));display:flex;align-items:center;justify-content:center;font-weight:800}
.pa img{position:absolute;inset:0;width:100%;height:100%;border-radius:50%;object-fit:cover}
.pt b{display:block;font-size:14px}
.pt small{display:block;font-size:12px;color:var(--secondary-text-color,#667085)}
.pt small.warn{color:var(--dl-red,#EF4444)}
.cat{margin-top:22px}
.ch{display:flex;align-items:center;gap:10px;margin:0 4px 10px;font-size:13px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--secondary-text-color,#667085);--mdc-icon-size:20px}
.ch ha-icon{color:var(--c)}
.ch small{font-weight:600;letter-spacing:0;text-transform:none}
.ty{display:flex;flex-wrap:wrap;align-items:center;gap:12px 20px;padding:14px;margin-bottom:10px;border-radius:20px;background:var(--card-background-color,#fff);box-shadow:var(--dl-shadow,0 3px 12px rgba(17,24,39,.08))}
.l{display:flex;align-items:center;gap:12px;flex:1 1 280px;min-width:0}
.ic{flex:none;width:44px;height:44px;border-radius:14px;display:flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--c) 20%,transparent);color:var(--c);--mdc-icon-size:24px;overflow:hidden}
.ic img{width:100%;height:100%;object-fit:cover;display:block}
.l b{display:block;font-size:15px}
.l small{display:block;margin-top:2px;font-size:12.5px;line-height:1.35;color:var(--secondary-text-color,#667085)}
.l small.m{font-size:11.5px;opacity:.85}
.tg{display:inline-block;margin-left:6px;padding:1px 7px;border-radius:8px;font-size:10.5px;font-weight:800;letter-spacing:.04em;vertical-align:1px;background:var(--dl-chip-bg,rgba(127,127,127,.16));color:var(--secondary-text-color,#667085)}
.r{display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px;flex:1 1 360px;justify-content:flex-end}
.who{display:flex;flex-wrap:wrap;gap:8px}
.pw{height:38px;padding:0 14px 0 8px;border-radius:19px;display:flex;align-items:center;gap:8px;font-size:13.5px;font-weight:700;background:var(--dl-chip-bg,rgba(127,127,127,.14));color:var(--secondary-text-color,#667085);transition:background .15s,color .15s}
.pw .av{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;background:rgba(127,127,127,.22);overflow:hidden;position:relative}
.pw .av img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.pw.on{background:var(--primary-color,#175CD3);color:var(--text-primary-color,#fff)}
.pw.on .av{background:rgba(255,255,255,.25)}
.sg{display:flex;padding:3px;border-radius:19px;background:var(--dl-chip-bg,rgba(127,127,127,.14))}
.sg button{height:32px;padding:0 13px;border-radius:16px;font-size:12.5px;font-weight:700;color:var(--secondary-text-color,#667085);white-space:nowrap}
.sg button.on{background:var(--card-background-color,#fff);color:var(--primary-text-color,#101B2D);box-shadow:0 1px 4px rgba(0,0,0,.18)}
.sg.off{opacity:.4;pointer-events:none}
.xb{display:flex;gap:4px}
.xb button{height:36px;padding:0 12px;border-radius:18px;display:flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;color:var(--secondary-text-color,#667085);--mdc-icon-size:17px}
.xb button:active,.xb button:hover{background:var(--dl-chip-bg,rgba(127,127,127,.14))}
.nop{font-size:12.5px;color:var(--secondary-text-color,#667085)}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);padding:10px 18px;border-radius:14px;background:var(--primary-text-color,#101B2D);color:var(--card-background-color,#fff);font-size:13.5px;font-weight:600;box-shadow:0 8px 30px rgba(0,0,0,.3);z-index:5}
.toast[hidden]{display:none}
.wait{padding:40px;text-align:center;color:var(--secondary-text-color,#667085)}`;
class EnhancedNotifyAdmin extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: 'open' }); }
  setConfig(c) { this._c = c || {}; }
  getCardSize() { return 12; }
  getGridOptions() { return { columns: 'full', rows: 'auto' }; }
  set hass(h) { this._h = h; N.setHass(h); }
  connectedCallback() {
    this._f = () => { cancelAnimationFrame(this._raf); this._raf = requestAnimationFrame(() => this._render()); };
    N.ls.add(this._f); this._render();
  }
  disconnectedCallback() { N.ls.delete(this._f); }
  _toast(t) {
    const el = this.shadowRoot.querySelector('.toast'); if (!el) return;
    el.textContent = t; el.hidden = false; clearTimeout(this._tt); this._tt = setTimeout(() => { el.hidden = true; }, 3500);
  }
  _render() {
    const sr = this.shadowRoot, s = N.snap;
    if (!sr.querySelector('.w')) {
      sr.innerHTML = `<style>${ACSS}</style><div class="w"><h1>Benachrichtigungen</h1><p class="lead">Lege pro Meldungstyp fest, wer eine Push-Nachricht erhält. Jede Meldung erscheint immer in der Glocke, der Push ist zusätzlich. Neue Typen tauchen hier automatisch auf, sobald sie zum ersten Mal ausgelöst werden.</p><div class="pp"></div><div class="body"></div></div><div class="toast" hidden></div>`;
      sr.querySelector('.w').addEventListener('click', (e) => this._click(e));
    }
    const body = sr.querySelector('.body'), pp = sr.querySelector('.pp');
    if (!s) { body.innerHTML = '<div class="wait">Verbindung zur Benachrichtigungszentrale wird aufgebaut …</div>'; return; }
    const persons = s.recipients || [];
    const ph = persons.map((p) => {
      const sv = p.active_services || [];
      return `<div class="pc"><span class="pa">${p.picture ? `<img src="${esc(p.picture)}" alt="">` : esc((p.name || '?').charAt(0).toUpperCase())}</span><span class="pt"><b>${esc(p.name)}</b>${sv.length ? `<small>${esc(sv.map((x) => x.replace(/^mobile_app_/, '').replace(/_/g, ' ')).join(', '))}</small>` : '<small class="warn">Kein Handy gefunden</small>'}</span></div>`;
    }).join('');
    if (pp.dataset.h !== ph) { pp.dataset.h = ph; pp.innerHTML = ph; }
    const types = Object.values(s.types || {});
    const cats = Object.keys(s.categories || {});
    const by = {}; types.forEach((t) => { (by[t.category] = by[t.category] || []).push(t); });
    Object.keys(by).forEach((k) => { if (!cats.includes(k)) cats.push(k); });
    const pOf = (id) => persons.find((p) => p.id === id);
    const html = cats.filter((k) => by[k]).map((k) => {
      const c = s.categories[k] || { name: k, icon: 'mdi:bell-outline', color: '#6B7280' };
      const rows = by[k].map((t) => {
        const eff = new Set(t.recipients_effective || []);
        const who = persons.map((p) => `<button class="pw${eff.has(p.id) ? ' on' : ''}" data-a="p" data-t="${esc(t.id)}" data-p="${esc(p.id)}" aria-pressed="${eff.has(p.id)}"><span class="av">${p.picture ? `<img src="${esc(p.picture)}" alt="">` : esc((p.name || '?').charAt(0).toUpperCase())}</span>${esc(p.name)}</button>`).join('');
        const none = eff.size === 0;
        const meta = t.count ? `Zuletzt ${esc(when(t.last))} · ${t.count}× ausgelöst` : 'Noch nie ausgelöst';
        return `<div class="ty" style="--c:${esc(c.color)}"><div class="l"><span class="ic">${iconHtml(t.icon)}</span><div><b>${esc(t.name)}${t.auto ? '<span class="tg">AUTOMATISCH ERKANNT</span>' : ''}</b>${t.description ? `<small>${esc(t.description)}</small>` : ''}<small class="m">${meta}</small></div></div><div class="r"><div class="who">${who}</div>${none ? '<span class="nop">Kein Push</span>' : ''}<div class="sg${none ? ' off' : ''}"><button class="${t.push_when === 'always' ? 'on' : ''}" data-a="w" data-t="${esc(t.id)}" data-w="always">Immer</button><button class="${t.push_when === 'away' ? 'on' : ''}" data-a="w" data-t="${esc(t.id)}" data-w="away">Nur unterwegs</button></div><div class="xb"><button data-a="test" data-t="${esc(t.id)}" title="Testmeldung senden"><ha-icon icon="mdi:send-outline"></ha-icon>Test</button>${t.customized ? `<button data-a="reset" data-t="${esc(t.id)}" title="Auf Standard zurücksetzen"><ha-icon icon="mdi:restore"></ha-icon>Standard</button>` : ''}</div></div></div>`;
      }).join('');
      return `<section class="cat" style="--c:${esc(c.color)}"><div class="ch"><ha-icon icon="${esc(c.icon)}"></ha-icon>${esc(c.name)}<small>${by[k].length} ${by[k].length === 1 ? 'Typ' : 'Typen'}</small></div>${rows}</section>`;
    }).join('');
    if (body.dataset.h !== html) { body.dataset.h = html; body.innerHTML = html; }
    void pOf;
  }
  async _click(e) {
    const b = e.target.closest('[data-a]'); if (!b || !N.snap) return;
    const t = N.snap.types[b.dataset.t]; if (!t) return;
    try {
      if (b.dataset.a === 'p') {
        const cur = new Set(t.recipients_effective || []);
        if (cur.has(b.dataset.p)) cur.delete(b.dataset.p); else cur.add(b.dataset.p);
        await N.call({ type: 'enhanced_notify/set_type', type_id: t.id, recipients: [...cur] });
      } else if (b.dataset.a === 'w') {
        await N.call({ type: 'enhanced_notify/set_type', type_id: t.id, push_when: b.dataset.w });
      } else if (b.dataset.a === 'reset') {
        await N.call({ type: 'enhanced_notify/set_type', type_id: t.id, reset: true });
        this._toast(`„${t.name}“ auf Standard zurückgesetzt`);
      } else if (b.dataset.a === 'test') {
        const now = new Date().toLocaleTimeString('de-DE');
        await this._h.callService('enhanced_notify', 'send', { type: t.id, title: `Test: ${t.name}`, message: `${t.example || t.name} (Test ${now})`, tag: `test:${t.id}` });
        this._toast('Testmeldung gesendet');
      }
    } catch (err) { this._toast(`Fehler: ${err && err.message ? err.message : err}`); }
  }
}
def('enhanced-notify-admin', EnhancedNotifyAdmin);
def('doralab-notify-admin', class extends EnhancedNotifyAdmin {}); // alter Kartenname (bis 0.3.x), entfällt in 2.0
reg('enhanced-notify-admin', 'Enhanced Notify (Admin)', 'Push je Meldungstyp und Person einstellen');
})();
