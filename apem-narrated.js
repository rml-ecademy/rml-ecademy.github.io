/* ECADEMY APEM narrated lesson player. FOR TRAINING AND EDUCATIONAL PURPOSES ONLY.
   One narration track, sections with start and end times taken from the recording, visuals and subtitles driven
   by the playback position, practice and knowledge checks per section, saved progress.
   The knowledge checks here are formative: they never unlock anything. Assessment is checked by the server. */
(() => {
  const CSS = `
.nv{display:grid;grid-template-columns:250px minmax(0,1fr);gap:18px;align-items:start;max-width:1180px}
.nv-nav{position:sticky;top:8px;background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:8px;max-height:calc(100vh - 24px);overflow:auto}
.nv-nav .sumline{color:var(--mute);font-size:.78rem;padding:4px 8px 8px}
.nv-nb{display:flex;gap:8px;align-items:baseline;width:100%;text-align:left;background:none;border:1px solid transparent;border-radius:8px;color:var(--ink);font:inherit;font-size:.88rem;padding:6px 8px;cursor:pointer}
.nv-nb:hover,.nv-nb:focus-visible{background:var(--panel2);outline:0}.nv-nb.on{background:var(--panel2);border-color:var(--accent)}
.nv-nb i{font:600 .74rem ui-monospace,Consolas,monospace;font-style:normal;color:var(--accent);min-width:20px}.nv-nb span{flex:1;min-width:0}
.nv-nb em{font-style:normal;font-size:.68rem;color:var(--lock);white-space:nowrap}.nv-nb.done em{color:var(--ok)}.nv-nb.part em{color:var(--warn)}
.nv-body{min-width:0}.nv-card{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:18px 20px}
.nv-tag{font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}.nv-card h2{margin:2px 0 10px}
.nv details{border:1px solid var(--rule);border-radius:10px;margin:10px 0;background:#1f2d3c}.nv details>summary{padding:10px 12px;font-weight:600;display:block}
.nv details>summary::before{content:'\\25B8';display:inline-block;width:1.2em;color:var(--accent)}.nv details[open]>summary::before{content:'\\25BE'}
.nv details>div,.nv details>ul{padding:0 14px 10px 14px;margin:0}.nv details>ul{padding-left:34px}.nv details p{margin:0 0 10px}.nv details li{margin:4px 0}
.nv-stage{border:1px solid var(--rule);border-radius:12px;background:#1d2b39;padding:14px;margin:12px 0 0}
.nv-stage [data-at]{opacity:.38;transition:opacity .35s,box-shadow .35s,border-color .35s}.nv-stage [data-at].seen,.nv-stage.all [data-at]{opacity:1}
.nv-stage [data-at].now{box-shadow:0 0 0 2px var(--accent)}.nv-stage.all [data-at].now{box-shadow:none}
.nv-photo{margin:0 0 12px}.nv-photo img{display:block;width:100%;height:auto;border-radius:8px;aspect-ratio:16/9;object-fit:cover;background:#000}.nv-photo figcaption{color:var(--mute);font-size:.74rem;margin-top:4px}
.nv-h{font-size:.74rem;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);margin:8px 0 6px}
.nv-line{border-left:3px solid var(--rule);background:var(--panel);border-radius:0 8px 8px 0;padding:8px 12px;margin:6px 0}.nv-line.key{border-left-color:var(--accent);font-weight:600}.nv-line.warn{border-left-color:var(--warn);color:#f3dfae}
.nv-chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}.nv-chip{border:1px solid var(--rule);background:var(--panel);border-radius:999px;padding:5px 12px;font-size:.9rem}
.nv-roles{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}.nv-role{background:var(--panel);border:1px solid var(--rule);border-radius:10px;padding:10px 12px}.nv-role b{display:block;color:var(--accent)}.nv-role span{font-size:.88rem}
.nv-paper{background:#f4f1e8;color:#1c2630;border-radius:8px;padding:14px 16px;font-family:Georgia,"Times New Roman",serif;box-shadow:0 2px 10px rgba(0,0,0,.35);margin-bottom:10px}
.nv-ph{font-weight:700;font-size:1.1rem;letter-spacing:.06em;border-bottom:2px solid #1c2630;padding-bottom:6px;margin-bottom:6px}.nv-ph small{display:block;font:600 .66rem ui-monospace,Consolas,monospace;color:#8a2f22;letter-spacing:.03em;margin-top:2px}
.nv-paper table{border-collapse:collapse;width:100%}.nv-paper th{text-align:left;font-weight:700;width:36%;vertical-align:top;padding:4px 8px 4px 4px}.nv-paper td{padding:4px}.nv-paper tr{border-bottom:1px solid #d9d3c1}
.nv-stage .nv-paper tr[data-at]{opacity:1}.nv-stage .nv-paper tr.now{box-shadow:none;background:#ffe9a8}.nv-stage .nv-paper tr.seen:not(.now){background:#f0ead6}
.nv-cmp{border-collapse:collapse;width:100%;margin:8px 0;font-size:.92rem}.nv-cmp th,.nv-cmp td{border:1px solid var(--rule);padding:6px 9px;text-align:left}.nv-cmp tr:first-child th{background:var(--panel2);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em}.nv-cmp td.chg{color:var(--warn);font-weight:600}
.nv-route,.nv-tl,.nv-flow{display:flex;gap:6px;margin:8px 0}.nv-node,.nv-tn,.nv-flow>div{flex:1;background:var(--panel);border:1px solid var(--rule);border-radius:10px;padding:10px;min-width:0;font-size:.88rem}
.nv-node i{display:block;height:4px;border-radius:2px;background:var(--accent);margin-bottom:8px}.nv-node.open i{background:var(--warn)}.nv-node b,.nv-tn b,.nv-flow b{display:block}.nv-node span,.nv-tn small{color:var(--mute);font-size:.8rem;display:block}
.nv-tn b{color:var(--accent)}.nv-tn.eta b{color:var(--ok)}.nv-tn span{display:block;font:600 .95rem ui-monospace,Consolas,monospace}.nv-flow b{color:var(--accent);font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px}
.nv-two{display:grid;grid-template-columns:1fr 1fr;gap:12px}.nv-calc{background:var(--panel);border:1px solid var(--rule);border-radius:10px;padding:10px 12px;margin:8px 0}.nv-calc>div[data-at]{font:1rem ui-monospace,Consolas,monospace;padding:2px 4px;border-radius:4px}.nv-calc .res{font-weight:700;color:var(--ok);border-top:1px solid var(--rule);margin-top:4px;padding-top:6px}
.nv-five{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.nv-five span{flex:1;text-align:center;font-weight:700;font-size:1.05rem;border:1px solid var(--accent);color:var(--accent);border-radius:10px;padding:10px 8px}
.nv-act{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.nv-stage .nv-act[data-at]{opacity:1;box-shadow:none}
.nv-dock{position:sticky;bottom:6px;z-index:2;margin:10px 0 4px;border-radius:10px;box-shadow:0 2px 14px rgba(0,0,0,.45)}
.nv-sub{min-height:3.2em;margin:0;padding:8px 12px;background:#101a24;border-radius:10px 10px 0 0;text-align:center;font-size:1.02rem;display:flex;align-items:center;justify-content:center}.nv-sub[hidden]{display:none}
.nv-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px;background:var(--panel2);border-radius:0 0 10px 10px}
.nv-sub[hidden]+.nv-bar{border-radius:10px}
.nv-bar input[type=range]{flex:1;min-width:120px;accent-color:var(--accent)}.nv-bar .tm{font:.8rem ui-monospace,Consolas,monospace;color:var(--mute);white-space:nowrap}
.nv-bar select{background:#16212c;color:var(--ink);border:1px solid var(--rule);border-radius:7px;padding:6px;font:inherit;font-size:.84rem}.nv-bar label{font-size:.8rem;color:var(--mute);display:inline-flex;gap:4px;align-items:center}
.nv h3{font-size:1rem;margin:18px 0 6px;letter-spacing:.02em}
.nv-w{background:var(--panel2);border-radius:10px;padding:12px 14px;margin:8px 0}.nv-w.good{outline:1px solid var(--ok)}.nv-q{font-weight:600;margin-bottom:8px}.nv-wi{color:var(--mute);font-size:.88rem;margin-bottom:8px}
.nv-o{display:flex;gap:8px;align-items:flex-start;padding:6px 8px;border-radius:8px;cursor:pointer}.nv-o:hover{background:var(--panel)}.nv-o input{margin-top:5px}.nv-o.good{background:#1f3a34}.nv-o.bad{background:#3d2622}
.nv-o small{display:block;color:var(--mute);font-size:.82rem;margin-top:2px}.nv-o.good small{color:var(--ok)}.nv-o.bad small{color:#ffb4a8}
.nv-fb{font-size:.9rem;margin-top:8px}.nv-fb.good{color:var(--ok)}.nv-fb.bad{color:#ffb4a8}
.nv-rows{width:100%;border-collapse:collapse}.nv-rows td{padding:7px 6px;border-top:1px solid var(--rule);vertical-align:top;font-size:.92rem}.nv-rows tr.good td:first-child{border-left:3px solid var(--ok)}.nv-rows tr.bad td:first-child{border-left:3px solid #ff9d8a}
.nv-rows select,.nv-rows input{background:#16212c;color:var(--ink);border:1px solid var(--rule);border-radius:7px;padding:6px 7px;font:inherit;font-size:.9rem;max-width:100%}.nv-rows input.hm{width:82px;font-family:ui-monospace,Consolas,monospace}.nv-rows input[type=number]{width:110px}
.nv-rows .rf{display:block;font-size:.82rem;margin-top:3px}.nv-rows tr.good .rf{color:var(--ok)}.nv-rows tr.bad .rf{color:#ffb4a8}.nv-rows .ctl{white-space:nowrap}
.nv-st{color:var(--mute);font-size:.86rem;flex:1;text-align:center}
@media (max-width:1000px){.nv{grid-template-columns:1fr}.nv-nav{position:static;display:flex;gap:4px;overflow-x:auto;max-height:none;padding:6px}.nv-nav .sumline{display:none}.nv-nb{width:auto;flex:0 0 auto;padding:6px 10px}.nv-nb span{display:none}.nv-nb em{display:none}.nv-nb.done i{color:var(--ok)}.nv-nb.part i{color:var(--warn)}}
@media (max-width:700px){.nv-two{grid-template-columns:1fr}.nv-route,.nv-tl,.nv-flow{flex-direction:column}.nv-card{padding:14px 12px}.nv-rows td{display:block;border-top:0;padding:3px 6px}.nv-rows tr{display:block;border-top:1px solid var(--rule);padding:6px 0}.nv-rows .ctl{white-space:normal}.nv-sub{font-size:.95rem}.nv-bar .tm.all{display:none}}
@media print{header,.disc,.owner,aside,.nv-bar,.nav{display:none!important}}`;
  let live = null;                                           // the lesson currently on screen
  const fmt = s => { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };

  function stop(){ if (live) { try { live.audio.pause(); live.flush(); } catch (_) {} live = null; } }

  function render(ctx){
    stop();
    if (!document.getElementById('nvcss')) { const st = document.createElement('style'); st.id = 'nvcss'; st.textContent = CSS; document.head.appendChild(st); }
    const { main, esc } = ctx, X = ctx.lesson.content, S = X.sections, code = ctx.lesson.code, LS = 'apem:narr:' + code + ':v' + (X.version || 1);
    const audio = new Audio(); audio.preload = 'metadata'; audio.src = X.audio.src;
    let prog = { v: 1, cur: 0, pos: 0, at: 0, s: {} }, cur = 0, cc = true, through = false, ended = false, saveT = null, raf = 0;
    const ans = {};                                          // widget answers kept while the lesson is open
    const flag = id => prog.s[id] || (prog.s[id] = {});
    const widgets = s => [...(s.practice || []), ...(s.check || [])];
    const secDone = s => { const f = flag(s.id); return !!f.h && (s.check || []).every(w => f.w && f.w[w.id]) && (s.practice || []).every(w => f.w && f.w[w.id]); };
    const secPart = s => { const f = flag(s.id); return !!f.h || !!(f.w && Object.keys(f.w).length); };
    function merge(o){ if (!o || typeof o !== 'object' || !o.s) return;
      for (const k of Object.keys(o.s)) { const f = flag(k), g = o.s[k] || {}; if (g.h) f.h = 1; if (g.w) { f.w = f.w || {}; for (const w of Object.keys(g.w)) f.w[w] = 1; } }
      if ((o.at || 0) > (prog.at || 0)) { prog.at = o.at; prog.cur = o.cur | 0; prog.pos = +o.pos || 0; } }
    function saveLocal(){ prog.cur = cur; prog.pos = Math.round(audio.currentTime * 10) / 10; prog.at = Date.now(); try { localStorage.setItem(LS, JSON.stringify(prog)); } catch (_) {} }
    function save(now){ saveLocal(); clearTimeout(saveT); const go = () => { ctx.saveProgress && ctx.saveProgress(code, prog).catch(() => {}); }; if (now) go(); else saveT = setTimeout(go, 2500); }
    const self = { audio, flush: () => { cancelAnimationFrame(raf); clearTimeout(saveT); saveLocal(); ctx.saveProgress && ctx.saveProgress(code, prog).catch(() => {}); } };
    live = self;

    main.innerHTML = `<h1>${esc(X.title)}</h1><p class="note">${esc(X.example_notice || '')}</p>
      <div class="nv"><nav class="nv-nav" id="nvNav" aria-label="Lesson sections"></nav><div class="nv-body" id="nvBody"></div></div>
      ${ctx.admin ? `<p class="note" style="margin-top:16px">Owner preview. ${esc(X.notice || '')}</p>` : ''}`;
    const nav = main.querySelector('#nvNav'), body = main.querySelector('#nvBody');

    function drawNav(){
      const n = S.filter(secDone).length;
      nav.innerHTML = `<div class="sumline">${n} of ${S.length} sections complete</div>` +
        (X.intro_video ? `<button class="nv-nb${cur === -1 ? ' on' : ''}" data-sec="-1"><i>00</i><span>${esc(X.intro_video.label)}</span><em></em></button>` : '') +
        S.map((s, i) => `<button class="nv-nb${i === cur ? ' on' : ''}${secDone(s) ? ' done' : secPart(s) ? ' part' : ''}" data-sec="${i}" title="${esc(s.title)}"><i>${String(s.n).padStart(2, '0')}</i><span>${esc(s.title)}</span><em>${secDone(s) ? 'Complete' : secPart(s) ? 'In progress' : ''}</em></button>`).join('');
      nav.querySelectorAll('[data-sec]').forEach(b => b.onclick = () => go(+b.dataset.sec, false));
      const on = nav.querySelector('.on'); if (on && on.scrollIntoView && nav.scrollWidth > nav.clientWidth) on.scrollIntoView({ block: 'nearest', inline: 'center' });
    }

    /* ----- widgets ----- */
    function wHtml(w){
      const a = ans[w.id] || (ans[w.id] = {});
      if (w.type === 'mcq') return `<div class="nv-w" data-w="${esc(w.id)}"><div class="nv-q">${esc(w.q)}</div>` +
        w.options.map((o, i) => `<label class="nv-o"><input type="${w.multi ? 'checkbox' : 'radio'}" name="${esc(w.id)}" value="${i}"${(a.sel || []).includes(i) ? ' checked' : ''}><span>${esc(o.t)}<small></small></span></label>`).join('') +
        `<div class="nav" style="margin-top:8px"><button class="b sm" data-chk>Check answer</button></div><div class="nv-fb" role="status"></div></div>`;
      if (w.type === 'assign') return `<div class="nv-w" data-w="${esc(w.id)}"><div class="nv-q">${esc(w.title)}</div><div class="nv-wi">${esc(w.intro || '')}</div><table class="nv-rows">` +
        w.rows.map((r, i) => `<tr data-i="${i}"><td>${esc(r.label)}<span class="rf"></span></td><td class="ctl">` + w.cols.map(c => `<select data-k="${esc(c.k)}" aria-label="${esc(c.label)}"><option value="">${esc(c.label)}</option>` +
          c.opts.map(([v, t]) => `<option value="${esc(v)}"${(a[i] || {})[c.k] === v ? ' selected' : ''}>${esc(t)}</option>`).join('') + `</select>`).join(' ') + `</td></tr>`).join('') +
        `</table><div class="nav" style="margin-top:8px"><button class="b sm" data-chk>Check answers</button></div><div class="nv-fb" role="status"></div></div>`;
      if (w.type === 'entries') return `<div class="nv-w" data-w="${esc(w.id)}"><div class="nv-q">${esc(w.title)}</div><div class="nv-wi">${esc(w.intro || '')}</div><table class="nv-rows">` +
        w.items.map((it, i) => { const v = a[i] || {}; return `<tr data-i="${i}"><td>${esc(it.label)}<span class="rf"></span></td><td class="ctl">` + (it.kind === 'dt'
          ? `<input type="date" data-p="d" value="${esc(v.d || '')}" aria-label="UTC date"> <input type="text" class="hm" data-p="t" inputmode="numeric" maxlength="5" placeholder="HH:MM" value="${esc(v.t || '')}" aria-label="UTC time, 24-hour"> UTC`
          : `<input type="number" step="any" inputmode="decimal" data-p="n" value="${esc(v.n ?? '')}" aria-label="${esc(it.label)}"> ${esc(it.unit || '')}`) + `</td></tr>`; }).join('') +
        `</table><div class="nav" style="margin-top:8px"><button class="b sm" data-chk>Check answers</button></div><div class="nv-fb" role="status"></div></div>`;
      return '';
    }
    const hm = v => { const m = String(v || '').trim().match(/^(\d{1,2})[:.]?(\d{2})$/); return m && +m[1] < 24 && +m[2] < 60 ? m[1].padStart(2, '0') + ':' + m[2] : ''; };
    function wWire(s, w){
      const el = body.querySelector(`[data-w="${w.id}"]`); if (!el) return;
      const a = ans[w.id], fb = el.querySelector('.nv-fb');
      const passed = ok => { if (ok) { const f = flag(s.id); f.w = f.w || {}; f.w[w.id] = 1; el.classList.add('good'); save(); drawNav(); status(); } };
      if (flag(s.id).w && flag(s.id).w[w.id]) el.classList.add('good');
      if (w.type === 'mcq') {
        el.querySelectorAll('input').forEach(i => i.onchange = () => { a.sel = [...el.querySelectorAll('input:checked')].map(x => +x.value); });
        el.querySelector('[data-chk]').onclick = () => {
          const sel = a.sel || []; el.querySelectorAll('.nv-o').forEach(l => { l.classList.remove('good', 'bad'); l.querySelector('small').textContent = ''; });
          if (!sel.length) { fb.className = 'nv-fb bad'; fb.textContent = w.multi ? 'Select at least one item.' : 'Select an answer.'; return; }
          let ok = true;
          w.options.forEach((o, i) => { const l = el.querySelectorAll('.nv-o')[i], on = sel.includes(i);
            if (on) { l.classList.add(o.ok ? 'good' : 'bad'); l.querySelector('small').textContent = o.fb; if (!o.ok) ok = false; }
            else if (w.multi && o.ok) ok = false; });
          fb.className = 'nv-fb ' + (ok ? 'good' : 'bad');
          fb.textContent = ok ? 'Correct.' : (w.multi && sel.every(i => w.options[i].ok) ? 'Correct so far. At least one more item applies.' : 'Not yet correct. Read the explanation and try again.');
          passed(ok);
        };
      } else if (w.type === 'assign') {
        el.querySelectorAll('tr[data-i]').forEach(tr => tr.querySelectorAll('select').forEach(sl => sl.onchange = () => { (a[tr.dataset.i] = a[tr.dataset.i] || {})[sl.dataset.k] = sl.value; }));
        el.querySelector('[data-chk]').onclick = () => { let good = 0;
          el.querySelectorAll('tr[data-i]').forEach(tr => { const r = w.rows[+tr.dataset.i], v = a[tr.dataset.i] || {}, ok = w.cols.every(c => v[c.k] === r.ans[c.k]), any = w.cols.some(c => v[c.k]);
            tr.classList.remove('good', 'bad'); tr.classList.add(ok ? 'good' : 'bad'); tr.querySelector('.rf').textContent = ok ? 'Correct. ' + r.fb : (any ? r.fb : 'Not answered.'); if (ok) good++; });
          const ok = good === w.rows.length; fb.className = 'nv-fb ' + (ok ? 'good' : 'bad'); fb.textContent = ok ? 'All correct.' : `${good} of ${w.rows.length} correct. Read the explanation beside each item and correct it.`; passed(ok); };
      } else if (w.type === 'entries') {
        el.querySelectorAll('tr[data-i]').forEach(tr => tr.querySelectorAll('input').forEach(inp => inp.oninput = inp.onchange = () => { (a[tr.dataset.i] = a[tr.dataset.i] || {})[inp.dataset.p] = inp.value; }));
        el.querySelector('[data-chk]').onclick = () => { let good = 0;
          el.querySelectorAll('tr[data-i]').forEach(tr => { const it = w.items[+tr.dataset.i], v = a[tr.dataset.i] || {};
            const any = it.kind === 'dt' ? (v.d || v.t) : (v.n !== undefined && v.n !== '');
            const ok = it.kind === 'dt' ? (v.d === it.ans.d && hm(v.t) === it.ans.t) : (any && Math.abs(Number(v.n) - it.ans) <= (it.tol || 0) + 1e-9);
            tr.classList.remove('good', 'bad'); tr.classList.add(ok ? 'good' : 'bad'); tr.querySelector('.rf').textContent = ok ? 'Correct. ' + it.fb : (any ? (it.kind === 'dt' && v.d !== it.ans.d && hm(v.t) === it.ans.t ? 'Check the date. ' : '') + it.fb : 'Not answered.'); if (ok) good++; });
          const ok = good === w.items.length; fb.className = 'nv-fb ' + (ok ? 'good' : 'bad'); fb.textContent = ok ? 'All correct.' : `${good} of ${w.items.length} correct. The method is shown beside each item.`; passed(ok); };
      }
    }

    /* ----- section ----- */
    let marks = [], stage = null, sub = null, rng = null, tmS = null, tmA = null, playB = null, stEl = null;
    function status(){ if (!stEl || cur < 0) return; const s = S[cur], f = flag(s.id), need = [];
      if (!f.h) need.push('listen to the narration'); if ((s.practice || []).some(w => !(f.w && f.w[w.id]))) need.push('complete the practice'); if ((s.check || []).some(w => !(f.w && f.w[w.id]))) need.push('answer the knowledge check');
      stEl.textContent = need.length ? 'To complete this section: ' + need.join(', ') + '.' : 'Section complete.'; }
    function draw(){
      drawNav();
      if (cur === -1) { const v = X.intro_video;
        body.innerHTML = `<div class="nv-card">` + (v.src ? `<video controls preload="metadata" playsinline style="width:100%;border-radius:8px;background:#000" src="${esc(v.src)}"></video>` : `<div class="pending" role="note">${esc(v.label)}<br>Pending production (${esc(v.code)}). Not yet available.</div>`) +
          `<div class="nav"><span class="nv-st"></span><button class="b" id="nvNext">Start the lesson</button></div></div>`;
        body.querySelector('#nvNext').onclick = () => go(0, false); marks = []; stage = sub = rng = null; return; }
      const s = S[cur];
      body.innerHTML = `<div class="nv-card"><div class="nv-tag">${esc(s.tag)}</div><h2>${String(s.n).padStart(2, '0')} ${esc(s.title)}</h2>
        <details open><summary>Learning objectives</summary><ul>${s.objectives.map(o => `<li>${esc(o)}</li>`).join('')}</ul></details>
        <div class="nv-stage" id="nvStage">${s.visual}</div>
        <div class="nv-dock"><div class="nv-sub" id="nvSub" aria-hidden="true"></div>
        <div class="nv-bar"><button class="b" id="nvPlay">Play</button><button class="b ghost sm" id="nvReplay">Replay section</button>
          <input type="range" id="nvRng" min="0" max="1000" value="0" aria-label="Position in this section"><span class="tm" id="nvTs"></span><span class="tm all" id="nvTa"></span>
          <select id="nvRate" aria-label="Playback speed"><option value="0.75">0.75x</option><option value="1" selected>1x</option><option value="1.25">1.25x</option><option value="1.5">1.5x</option></select>
          <label><input type="checkbox" id="nvCc"${cc ? ' checked' : ''}> Subtitles</label><label><input type="checkbox" id="nvThru"${through ? ' checked' : ''}> Play through</label></div></div>
        ${s.explain.map(x => `<details><summary>${esc(x.h)}</summary><div>${x.html}</div></details>`).join('')}
        ${(s.practice || []).length ? `<h3>Practice</h3>` + s.practice.map(wHtml).join('') : ''}
        ${(s.check || []).length ? `<h3>Knowledge check</h3>` + s.check.map(wHtml).join('') : ''}
        <div class="nav"><button class="b ghost" id="nvPrev"${cur === 0 && !X.intro_video ? ' disabled' : ''}>Previous</button><span class="nv-st" id="nvSt"></span>${cur < S.length - 1 ? '<button class="b" id="nvNext">Next section</button>' : '<button class="b" id="nvDone">Back to course map</button>'}</div></div>`;
      const q = id => body.querySelector('#' + id);
      stage = q('nvStage'); sub = q('nvSub'); rng = q('nvRng'); tmS = q('nvTs'); tmA = q('nvTa'); playB = q('nvPlay'); stEl = q('nvSt');
      marks = [...stage.querySelectorAll('[data-at]')].map(el => ({ el, at: +el.dataset.at })).sort((a, b) => a.at - b.at);
      sub.hidden = !cc; q('nvRate').value = String(audio.playbackRate);
      playB.onclick = () => { if (audio.paused) { if (audio.currentTime >= s.end - 0.15 || audio.currentTime < s.start - 0.05) audio.currentTime = s.start; ended = false; audio.play().catch(() => {}); } else audio.pause(); };
      q('nvReplay').onclick = () => { audio.currentTime = s.start; ended = false; audio.play().catch(() => {}); };
      rng.oninput = () => { audio.currentTime = s.start + (s.end - s.start - 0.05) * rng.value / 1000; ended = false; tick(); };
      q('nvRate').onchange = e => { audio.playbackRate = +e.target.value; };
      q('nvCc').onchange = e => { cc = e.target.checked; sub.hidden = !cc; };
      q('nvThru').onchange = e => { through = e.target.checked; };
      q('nvPrev').onclick = () => go(cur - 1, false);
      if (q('nvNext')) q('nvNext').onclick = () => go(cur + 1, false);
      if (q('nvDone')) q('nvDone').onclick = () => { stop(); ctx.overview(); };
      stage.querySelectorAll('[data-open]').forEach(b => b.onclick = () => { stop(); ctx.open(b.dataset.open); });
      stage.querySelectorAll('[data-record]').forEach(b => b.onclick = () => { stop(); ctx.record(b.dataset.record); });
      for (const w of widgets(s)) wWire(s, w);
      status(); tick();
    }
    function go(i, keepPlaying){
      if (i < (X.intro_video ? -1 : 0) || i >= S.length) return;
      const was = !audio.paused && keepPlaying; if (!keepPlaying) audio.pause();
      cur = i; ended = false;
      if (i >= 0 && !was) { try { audio.currentTime = S[i].start; } catch (_) {} }
      draw(); save(); if (!keepPlaying) main.focus();
    }
    function tick(){
      if (live !== self || cur < 0 || !stage) return;
      if (!document.body.contains(stage)) { stop(); return; }
      const s = S[cur], t = audio.currentTime, f = flag(s.id);
      if (!audio.paused && t >= s.end - 0.03) {                       // end of this section's narration
        if (!f.h) { f.h = 1; save(); drawNav(); status(); }
        if (through && cur < S.length - 1) { cur++; draw(); save(); return; }
        audio.pause(); ended = true; try { audio.currentTime = s.end - 0.04; } catch (_) {}
      }
      const inSec = t >= s.start - 0.05 && t <= s.end + 0.05, rel = Math.min(1, Math.max(0, (t - s.start) / (s.end - s.start)));
      const showAll = ended || (f.h && audio.paused && rel < 0.002);   // finished, or a completed section not yet replayed
      stage.classList.toggle('all', !!showAll);
      let last = null; for (const m of marks) { const on = inSec && t >= m.at - 0.05; m.el.classList.toggle('seen', on); m.el.classList.remove('now'); if (on) last = m; }
      if (last && !showAll) for (const m of marks) if (m.at === last.at) m.el.classList.add('now');
      if (sub && cc) { const c = inSec && !ended ? s.cues.find(c => t >= c[0] - 0.02 && t < c[1]) : null; const txt = c ? c[2] : ''; if (sub.textContent !== txt) sub.textContent = txt; }
      if (document.activeElement !== rng) rng.value = Math.round(rel * 1000);
      tmS.textContent = fmt(t - s.start) + ' / ' + fmt(s.end - s.start); tmA.textContent = 'Lesson ' + fmt(t) + ' / ' + fmt(X.audio.duration);
      playB.textContent = audio.paused ? (ended ? 'Play again' : 'Play') : 'Pause';
    }
    const loop = () => { tick(); if (live === self && !audio.paused) raf = requestAnimationFrame(loop); };
    audio.addEventListener('play', () => { cancelAnimationFrame(raf); loop(); });
    audio.addEventListener('pause', () => { tick(); save(); });
    audio.addEventListener('timeupdate', tick); audio.addEventListener('seeked', tick);
    audio.addEventListener('ended', () => { const s = S[S.length - 1]; if (!flag(s.id).h) { flag(s.id).h = 1; save(true); drawNav(); } ended = true; tick(); });
    audio.addEventListener('error', () => { if (sub) { sub.hidden = false; sub.textContent = 'The narration could not be loaded. Check your connection and try again.'; } });

    /* ----- start: restore progress from this device, then from the account ----- */
    try { merge(JSON.parse(localStorage.getItem(LS) || 'null')); } catch (_) {}
    const start = () => { cur = Math.min(S.length - 1, Math.max(0, prog.cur | 0)); const p = +prog.pos || 0;
      draw(); if (p > S[cur].start && p < S[cur].end - 0.5) { const set = () => { try { audio.currentTime = p; } catch (_) {} tick(); }; audio.readyState >= 1 ? set() : audio.addEventListener('loadedmetadata', set, { once: true }); } };
    start();
    if (ctx.loadProgress) ctx.loadProgress(code).then(o => { if (live !== self || !o) return; const before = prog.at; merge(o); if (audio.paused && prog.at !== before) start(); else drawNav(); }).catch(() => {});
    window.addEventListener('pagehide', () => { if (live === self) saveLocal(); });
  }
  window.APEM_NARRATED = { render, stop };
})();
