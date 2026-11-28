/* ECADEMY maintenance pause.
   The owner switches it on in the admin page; every student page then shows a full-screen notice
   and stays paused until it is switched off again. The owner account is let through (checked on the server). */
(function () {
  if (window.top !== window.self) return;                       // simulators inside the hub: the hub page handles it
  var URL_ = 'https://eazrfhrbhftskcrffjun.supabase.co/rest/v1/rpc/site_status';
  var KEY = 'sb_publishable_i1yPRozADgoCxDsU676f_A_bISeo-4I';   // publishable key: safe in the browser
  var STORES = ['ecademy-admin-auth', 'sb-eazrfhrbhftskcrffjun-auth-token'];
  var EVERY = 60000, box = null, pill = null, prevOverflow = null;

  function tokens() {
    var out = [];
    STORES.forEach(function (k) {
      try { var s = JSON.parse(localStorage.getItem(k) || 'null'); if (s && s.access_token && (!s.expires_at || s.expires_at * 1000 > Date.now())) out.push(s.access_token); } catch (_) {}
    });
    return out;
  }
  function ask(token) {
    return fetch(URL_, { method: 'POST', cache: 'no-store', headers: { apikey: KEY, Authorization: 'Bearer ' + (token || KEY), 'Content-Type': 'application/json' }, body: '{}' })
      .then(function (r) { if (!r.ok) throw new Error('status ' + r.status); return r.json(); });
  }
  function status() {                                            // owner if any saved login on this device is an admin
    var t = tokens();
    if (!t.length) return ask(null);
    return Promise.all(t.map(function (x) { return ask(x).catch(function () { return null; }); })).then(function (rs) {
      rs = rs.filter(Boolean);
      if (!rs.length) return ask(null);
      return rs.filter(function (r) { return r.admin; })[0] || rs[0];
    });
  }

  function el(tag, css, text) { var e = document.createElement(tag); e.style.cssText = css; if (text != null) e.textContent = text; return e; }
  function stopMedia() { try { document.querySelectorAll('video,audio').forEach(function (m) { m.pause(); }); } catch (_) {} }

  function block(msg) {
    if (!document.body) return;
    if (!box) {
      box = el('div', 'position:fixed;inset:0;z-index:2147483647;background:#EEF3F7;display:flex;align-items:center;justify-content:center;padding:24px;font-family:"Albert Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#0C2D48');
      box.setAttribute('role', 'alertdialog'); box.setAttribute('aria-modal', 'true'); box.setAttribute('aria-label', 'ECADEMY maintenance notice');
      var card = el('div', 'width:min(520px,100%);background:#fff;border:1px solid #D3E2E9;border-radius:18px;padding:32px 26px;text-align:center;box-shadow:0 12px 40px rgba(12,45,72,.12)');
      card.appendChild(el('div', 'font-weight:800;letter-spacing:.18em;font-size:.8rem;color:#5E7587;margin-bottom:14px', 'ECADEMY'));
      card.appendChild(el('div', 'width:44px;height:3px;background:#B9821A;border-radius:2px;margin:0 auto 18px'));
      card.appendChild(el('h1', 'margin:0 0 12px;font-size:1.45rem;line-height:1.25;font-weight:800', 'System maintenance in progress'));
      var m = el('p', 'margin:0 0 16px;font-size:1.02rem;line-height:1.55;color:#2B4659;white-space:pre-wrap;word-break:break-word'); m.id = 'ecademyMaintMsg'; card.appendChild(m);
      card.appendChild(el('p', 'margin:0;font-size:.88rem;line-height:1.5;color:#5E7587', 'Your account and your progress are safe. This page will open again by itself as soon as the update is finished.'));
      box.appendChild(card);
      prevOverflow = document.documentElement.style.overflow;
      document.documentElement.style.overflow = 'hidden';
      document.body.appendChild(box);
    }
    box.querySelector('#ecademyMaintMsg').textContent = msg || 'ECADEMY is being updated and is paused for a short time. Please come back a little later.';
    stopMedia();
  }
  function unblock() { if (box) { box.remove(); box = null; document.documentElement.style.overflow = prevOverflow || ''; } }
  function ownerPill(on) {
    if (!on) { if (pill) { pill.remove(); pill = null; } return; }
    if (pill || !document.body) return;
    pill = el('a', 'position:fixed;left:50%;bottom:12px;transform:translateX(-50%);z-index:2147483646;background:#B3261E;color:#fff;font:700 .8rem system-ui,sans-serif;padding:8px 14px;border-radius:999px;text-decoration:none;box-shadow:0 4px 14px rgba(0,0,0,.25);white-space:nowrap', 'Maintenance ON · students are paused');
    pill.href = '/approve.html';
    document.body.appendChild(pill);
  }

  function check() {
    status().then(function (s) {
      if (!s) return;
      if (s.on && !s.admin) { ownerPill(false); block(s.message); }
      else { unblock(); ownerPill(!!s.on); }
    }).catch(function () {});                                    // cannot reach the server: leave the page as it is
  }
  function start() { check(); setInterval(check, EVERY); document.addEventListener('visibilitychange', function () { if (!document.hidden) check(); }); }
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
})();
