"""Phase 7 - Dashboard generator (interactive, static HTML).

Reads the DuckDB warehouse and produces a single self-contained HTML file
(dashboard/index.html). Incident-level data is embedded in the page, so the
dashboard has LIVE FILTERS - severity, incident type, weather - and every
chart and KPI recomputes instantly in the browser. No server needed.

Regenerate after every warehouse rebuild:
    python dashboard/build_dashboard.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "resqstats.duckdb"
OUT = ROOT / "dashboard" / "index.html"


def fetch_rows() -> list[dict]:
    con = duckdb.connect(str(DB), read_only=True)
    rows = con.sql("""
        select town, incident_type, severity, call_hour,
               minutes_to_scene, total_minutes, station, is_raining
        from fct_incidents
    """).fetchall()
    con.close()
    return [
        {"town": r[0], "type": r[1], "sev": r[2], "hour": int(r[3]),
         "resp": float(r[4]), "total": float(r[5]), "station": r[6], "rain": bool(r[7])}
        for r in rows
    ]


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ResQStats — Karachi Ambulance Dispatch Analytics</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  :root { --bg:#0f1419; --card:#1a2129; --text:#e6edf3; --muted:#8b98a5; --accent:#e53935; --line:#2a3441; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--text); font-family:'Segoe UI',system-ui,sans-serif; padding:24px; }
  h1 { font-size:26px; } h1 span { color:var(--accent); }
  .filters { display:flex; flex-wrap:wrap; gap:10px; align-items:center;
             background:var(--card); border:1px solid var(--line); border-radius:10px;
             padding:12px 14px; margin:18px 0; }
  .filters .lbl { color:var(--muted); font-size:13px; margin-right:2px; }
  .chip { background:#232d38; color:var(--text); border:1px solid var(--line); border-radius:16px;
          padding:5px 13px; font-size:13px; cursor:pointer; user-select:none; transition:all .15s; }
  .chip.on { border-color:var(--accent); background:#3a2326; color:#ff8a80; font-weight:600; }
  select { background:#232d38; color:var(--text); border:1px solid var(--line); border-radius:8px;
           padding:6px 10px; font-size:13px; cursor:pointer; }
  .reset { margin-left:auto; background:none; border:1px solid var(--line); color:var(--muted);
           border-radius:8px; padding:6px 12px; font-size:13px; cursor:pointer; }
  .reset:hover { color:var(--text); }
  .count { color:var(--muted); font-size:13px; }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; margin-bottom:14px; }
  .kpi { background:var(--card); border-radius:10px; padding:18px; border:1px solid var(--line); }
  .kpi .v { font-size:30px; font-weight:700; } .kpi .l { color:var(--muted); font-size:13px; margin-top:4px; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
  .card { background:var(--card); border-radius:10px; padding:14px; border:1px solid var(--line); }
  .card.wide { grid-column:1 / -1; }
  h2 { font-size:15px; margin:4px 6px 10px; font-weight:600; }
  footer { color:var(--muted); font-size:12px; margin-top:20px; text-align:center; }
  @media (max-width:900px) { .grid { grid-template-columns:1fr; } }
</style>
</head>
<body>
<h1>🚑 ResQ<span>Stats</span> — Karachi Ambulance Dispatch Analytics</h1>

<div class="filters">
  <span class="lbl">Severity:</span>
  <span class="chip on" data-sev="critical">critical</span>
  <span class="chip on" data-sev="serious">serious</span>
  <span class="chip on" data-sev="moderate">moderate</span>
  <span class="chip on" data-sev="minor">minor</span>
  <span class="lbl" style="margin-left:10px">Type:</span>
  <select id="f_type"><option value="all">all types</option></select>
  <span class="lbl" style="margin-left:10px">Weather:</span>
  <select id="f_rain">
    <option value="all">all weather</option>
    <option value="dry">dry days</option>
    <option value="rain">rainy days</option>
  </select>
  <span class="count" id="f_count" style="margin-left:10px"></span>
  <button class="reset" id="f_reset">Reset filters</button>
</div>

<div class="kpis">
  <div class="kpi"><div class="v" id="k_inc"></div><div class="l">Emergency incidents</div></div>
  <div class="kpi"><div class="v" id="k_resp"></div><div class="l">Median response time</div></div>
  <div class="kpi"><div class="v" id="k_p90"></div><div class="l">P90 response time</div></div>
  <div class="kpi"><div class="v" id="k_gold"></div><div class="l">Golden hour (critical ≤ 60 min)</div></div>
  <div class="kpi"><div class="v" id="k_towns"></div><div class="l">Towns covered</div></div>
</div>

<div class="grid">
  <div class="card wide"><h2>Coverage gaps — response time by town (median &amp; P90 minutes)</h2><div id="c_coverage" style="height:480px"></div></div>
  <div class="card"><h2>Demand &amp; response by hour of day</h2><div id="c_hourly" style="height:380px"></div></div>
  <div class="card"><h2>Incident types</h2><div id="c_types" style="height:380px"></div></div>
  <div class="card"><h2>Severity mix</h2><div id="c_sev" style="height:360px"></div></div>
  <div class="card"><h2>Station load heatmap (dispatches by hour)</h2><div id="c_heat" style="height:360px"></div></div>
</div>

<footer>Generated __GENERATED__ · simulated data (real dispatch data is confidential)</footer>

<script>
const ROWS = __DATA__;
const SEVS = ['critical','serious','moderate','minor'];
const SEV_COLOR = {critical:'#e53935', serious:'#fb8c00', moderate:'#fdd835', minor:'#43a047'};
const state = { sev:new Set(SEVS), type:'all', rain:'all' };

const L = { paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
  font:{color:'#e6edf3', size:12}, margin:{t:10,r:20,b:40,l:120},
  xaxis:{gridcolor:'#2a3441'}, yaxis:{gridcolor:'#2a3441'} };
const CFG = {displayModeBar:false, responsive:true};

const median = a => { if(!a.length) return 0; const s=[...a].sort((x,y)=>x-y), m=Math.floor(s.length/2);
  return s.length%2 ? s[m] : (s[m-1]+s[m])/2; };
const q90 = a => { if(!a.length) return 0; const s=[...a].sort((x,y)=>x-y);
  return s[Math.min(s.length-1, Math.floor(0.9*(s.length-1)+0.999))]; };
const r1 = x => Math.round(x*10)/10;

// populate type dropdown
[...new Set(ROWS.map(r=>r.type))].sort().forEach(t => {
  const o=document.createElement('option'); o.value=t; o.textContent=t.replace('_',' ');
  document.getElementById('f_type').appendChild(o);
});

function filtered() {
  return ROWS.filter(r => state.sev.has(r.sev)
    && (state.type==='all' || r.type===state.type)
    && (state.rain==='all' || (state.rain==='rain') === r.rain));
}

function render() {
  const rows = filtered();
  document.getElementById('f_count').textContent = rows.length + ' of ' + ROWS.length + ' incidents';

  // KPIs
  const resp = rows.map(r=>r.resp);
  const crit = rows.filter(r=>r.sev==='critical');
  const gold = crit.length ? Math.round(100*crit.filter(r=>r.total<=60).length/crit.length) : 0;
  document.getElementById('k_inc').textContent  = rows.length;
  document.getElementById('k_resp').textContent = r1(median(resp)) + ' min';
  document.getElementById('k_p90').textContent  = r1(q90(resp)) + ' min';
  document.getElementById('k_gold').textContent = crit.length ? gold + '%' : '—';
  document.getElementById('k_towns').textContent= new Set(rows.map(r=>r.town)).size;

  // Coverage by town
  const byTown = {};
  rows.forEach(r => (byTown[r.town] = byTown[r.town] || []).push(r.resp));
  const towns = Object.keys(byTown).map(t => ({t, m:r1(median(byTown[t])), p:r1(q90(byTown[t]))}))
    .sort((a,b) => a.m - b.m);
  const colors = towns.map(x => x.t==='Baldia' ? '#e53935' : (x.m>20 ? '#fb8c00' : '#43a047'));
  Plotly.react('c_coverage', [
    {type:'bar', orientation:'h', y:towns.map(x=>x.t), x:towns.map(x=>x.m),
     marker:{color:colors}, name:'Median', hovertemplate:'%{y}: %{x} min<extra>median</extra>'},
    {type:'scatter', mode:'markers', y:towns.map(x=>x.t), x:towns.map(x=>x.p),
     marker:{color:'#8b98a5', size:9, symbol:'line-ns-open'}, name:'P90',
     hovertemplate:'%{y}: %{x} min<extra>P90</extra>'}
  ], {...L, showlegend:true, legend:{orientation:'h', y:1.06},
     shapes:[{type:'line', x0:15, x1:15, y0:-0.5, y1:towns.length-0.5,
              line:{color:'#8b98a5', dash:'dash', width:1}}]}, CFG);

  // Hourly
  const hours = [...Array(24).keys()];
  const hc = hours.map(h => rows.filter(r=>r.hour===h).length);
  const hr = hours.map(h => { const v=rows.filter(r=>r.hour===h).map(r=>r.resp);
    return v.length ? r1(v.reduce((a,b)=>a+b,0)/v.length) : null; });
  Plotly.react('c_hourly', [
    {type:'bar', x:hours, y:hc, name:'Incidents', marker:{color:'#3949ab'}},
    {type:'scatter', mode:'lines+markers', x:hours, y:hr, name:'Avg response (min)',
     yaxis:'y2', line:{color:'#e53935', width:2}, connectgaps:true}
  ], {...L, margin:{t:10,r:60,b:40,l:50}, xaxis:{...L.xaxis, title:'hour of day', dtick:2},
     yaxis2:{overlaying:'y', side:'right', gridcolor:'rgba(0,0,0,0)', color:'#e57373'},
     legend:{orientation:'h', y:1.1}}, CFG);

  // Types
  const byType = {};
  rows.forEach(r => byType[r.type] = (byType[r.type]||0)+1);
  const types = Object.entries(byType).sort((a,b)=>b[1]-a[1]);
  Plotly.react('c_types', [{type:'bar', x:types.map(t=>t[1]), y:types.map(t=>t[0].replace('_',' ')),
    orientation:'h', marker:{color:'#00897b'}, hovertemplate:'%{y}: %{x}<extra></extra>'}],
    {...L, yaxis:{...L.yaxis, autorange:'reversed'}}, CFG);

  // Severity donut
  const sevCounts = SEVS.map(s => rows.filter(r=>r.sev===s).length);
  Plotly.react('c_sev', [{type:'pie', hole:0.55, labels:SEVS, values:sevCounts,
    marker:{colors:SEVS.map(s=>SEV_COLOR[s])}, textinfo:'label+percent'}],
    {...L, margin:{t:10,r:10,b:10,l:10}, showlegend:false}, CFG);

  // Station heatmap
  const stations = [...new Set(rows.map(r=>r.station))].sort();
  const z = stations.map(s => hours.map(h => rows.filter(r=>r.station===s && r.hour===h).length));
  Plotly.react('c_heat', [{type:'heatmap', z, y:stations, x:hours, colorscale:'YlOrRd',
    showscale:false, hovertemplate:'%{y} · %{x}:00 — %{z} dispatches<extra></extra>'}],
    {...L, xaxis:{...L.xaxis, title:'hour of day', dtick:2}}, CFG);
}

// wire up controls
document.querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => {
  const s = c.dataset.sev;
  if (state.sev.has(s) && state.sev.size > 1) { state.sev.delete(s); c.classList.remove('on'); }
  else { state.sev.add(s); c.classList.add('on'); }
  render();
}));
document.getElementById('f_type').addEventListener('change', e => { state.type = e.target.value; render(); });
document.getElementById('f_rain').addEventListener('change', e => { state.rain = e.target.value; render(); });
document.getElementById('f_reset').addEventListener('click', () => {
  state.sev = new Set(SEVS); state.type='all'; state.rain='all';
  document.querySelectorAll('.chip').forEach(c=>c.classList.add('on'));
  document.getElementById('f_type').value='all'; document.getElementById('f_rain').value='all';
  render();
});

render();
</script>
</body>
</html>
"""


def main() -> None:
    rows = fetch_rows()
    data = json.dumps(rows, separators=(",", ":"))
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = TEMPLATE.replace("__DATA__", data).replace("__GENERATED__", generated)
    OUT.write_text(html, encoding="utf-8")
    print(f"dashboard written -> {OUT} ({len(html)//1024} KB), {len(rows)} incidents embedded")


if __name__ == "__main__":
    main()
