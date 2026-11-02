'use strict';
(() => {
  const el = id => document.getElementById(id);
  let pending = null, generation = 0;
  const pct = x => Number.isFinite(x) ? x.toFixed(1) + '%' : '—';
  const when = x => x && Number.isFinite(Date.parse(x)) ? new Date(x).toLocaleString('it-IT', {timeZone:'Europe/Rome'}) : '—';
  function clear() {
    for (const id of ['summary','markets','coverage','scans','issues','attempts']) el(id).replaceChildren();
    el('data').hidden = true;
  }
  function row(id, values) {
    const tr = document.createElement('tr');
    for (const value of values) { const td = document.createElement('td'); td.textContent = value ?? '—'; tr.append(td); }
    el(id).append(tr);
  }
  el('logout').addEventListener('click', () => {
    generation++; pending?.abort(); pending = null; el('key').value = ''; clear(); el('status').textContent = 'Accesso chiuso.'; el('load').disabled = false;
  });
  el('login').addEventListener('submit', async event => {
    event.preventDefault(); pending?.abort(); const current = ++generation;
    const controller = new AbortController(); pending = controller;
    const timeout = setTimeout(() => controller.abort(), 15000);
    clear(); el('load').disabled = true; el('status').textContent = 'Caricamento…';
    try {
      const result = await fetch('/api/admin/monitor', {headers:{Authorization:'Bearer ' + el('key').value}, cache:'no-store', credentials:'omit', signal:controller.signal});
      if (!result.ok) throw Error(result.status === 401 ? 'Chiave non valida.' : 'Monitoraggio temporaneamente non disponibile.');
      const data = await result.json(); if (current !== generation) return;
      const expected = data.coverage.reduce((n,r) => n+r.expected, 0), matched = data.coverage.reduce((n,r) => n+r.matched, 0);
      for (const value of [matched + ' / ' + expected + ' linee abbinate', pct(expected ? 100*matched/expected : null) + ' copertura', Object.values(data.odds_requests_24h).reduce((n,x) => n+x, 0) + ' richieste HTTP / 24h']) {
        const card = document.createElement('div'); card.className = 'card'; card.textContent = value; el('summary').append(card);
      }
      el('note').textContent = data.calibration_note;
      for (const r of data.calibration.filter(r => r.probability_bin === 'all')) row('markets', [r.market,r.n,pct(r.estimated_pct),pct(r.observed_pct),r.brier]);
      for (const r of data.coverage) row('coverage', [r.date,r.expected,r.matched,r.gap,pct(r.coverage_pct)]);
      for (const r of data.scans) {
        row('scans', [r.date,r.state,when(r.odds_fetched_at),r.odds_source,r.http_requests,r.quote_lines,r.timings.totale_s == null ? '—' : r.timings.totale_s + ' s']);
        if (r.issues.length) { const li = document.createElement('li'); li.className = 'warn'; li.textContent = r.date + ' · ' + when(r.saved_at) + ': ' + r.issues.join('; '); el('issues').append(li); }
      }
      for (const r of data.attempts) row('attempts', [r.date,r.state,r.stage,when(r.heartbeat_at)]);
      el('data').hidden = false; el('status').textContent = 'Aggiornato: ' + when(data.generated_at);
    } catch (error) {
      if (current === generation) { clear(); el('status').textContent = error.name === 'AbortError' ? 'Tempo di attesa scaduto. Riprova.' : error.message; }
    } finally { clearTimeout(timeout); if (current === generation) { el('load').disabled = false; pending = null; } }
  });
})();
