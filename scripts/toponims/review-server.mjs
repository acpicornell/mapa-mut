// Local toponym curation tool — SINGLE-SHEET, three views over ONE data model:
//   • Taula  : an editable grid (fast bulk edits).
//   • Fitxes : one item at a time with the engraving crop + NGIB candidates + map.
//   • Mapa   : all toponyms on a geographic layer.
// All three derive from buildItems() — a SINGLE source-of-truth record per toponym
// (matches.json base + toponims.json geometry + curation.json overlay + flags +
// recheck candidates). No field is merged twice, so the views can't disagree.
// This map (Vicenç Mut, 1683) is ONE sheet: all data lives directly under
// data/toponims/ (no quadrant subdirectory). ALL hand edits persist to a SINGLE
// overlay — data/toponims/curation.json — one record per toponym id:
//   { "B01_1": { "graf": "...", "tipus": [...], "ordre": [...], "ngib": "...", "verdict": "ok|pick|none|trash" } }
//
//   node scripts/toponims/review-server.mjs   ->  http://localhost:4400/
import http from 'node:http';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const DATA = `${ROOT}/data/toponims`;
// Single-sheet data paths (no <q> quadrant dimension).
const F = {
  matches: `${DATA}/matches.json`,     // flat list; NO geometry — JOIN to toponims by id
  toponims: `${DATA}/toponims.json`,   // {toponims:[{id,x,y,lon,lat,dubte,…}]}
  recheck: `${DATA}/recheck.json`,     // flat list [{id,…,candidates:[{grafia,municipi,km,sim}]}]
  crops: `${DATA}/review-crops`,       // optional engraving crops (degrade gracefully if absent)
  curation: `${DATA}/curation.json`,   // SINGLE overlay: {id: {graf?, tipus?, ordre?, ngib?, verdict?}}
  flags: `${DATA}/quality_flags.json`, // optional {id:[codes]} from quality_audit.py
  ngib: `${DATA}/ngib/llocs.json`,     // NGIB gazetteer [{grafia,tipus,municipi,nucli,lng,lat}]
};
// Missing file -> default. EXISTING but corrupt -> THROW (never silently return the
// default, which would let the next write clobber hand-curation with an empty object).
const readJSON = (p, d) => (fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : d);
// Atomic write (tmp + rename) with a rolling .bak of the previous good file, so a crash
// mid-write — or a corrupt read upstream — can never destroy accumulated curation.
const writeJSON = (p, o) => {
  const tmp = `${p}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(o, null, 1));
  try { if (fs.existsSync(p)) fs.copyFileSync(p, `${p}.bak`); } catch {}
  fs.renameSync(tmp, p);
};
const NGIB = JSON.parse(fs.readFileSync(F.ngib, 'utf8'));
const NGIB_JSON = JSON.stringify(NGIB.map((g) => [g.grafia, g.municipi, g.lng, g.lat]));
// grafia municipi -> [lng,lat], to give recheck candidates (which carry no
// position) coordinates for the card mini-map. First occurrence wins.
const NGIB_POS = (() => {
  const m = new Map();
  for (const g of NGIB) { const k = `${g.grafia} ${g.municipi}`; if (!m.has(k)) m.set(k, [g.lng, g.lat]); if (!m.has(g.grafia)) m.set(g.grafia, [g.lng, g.lat]); }
  return m;
})();

// SINGLE SOURCE OF TRUTH for the sheet's toponyms. Every view (table, card, geo)
// derives from this — no field is merged twice with divergent logic. Layers:
//   matches.json   = authoritative base (graf/nom/tipus/ordre/decision/review/ngib/…)
//   toponims.json  = geometry (x,y crop px · lon,lat WGS84 · dubte)
//   curation.json  = hand-edit overlay (graf/tipus/ordre/ngib-pick/verdict), applied here
//   recheck.json   = ONLY the nearby NGIB candidates (its other fields are a stale snapshot)
//   quality_flags  = audit flags
function buildItems() {
  const matches = readJSON(F.matches, []);
  const cur = readJSON(F.curation, {});
  const geoById = Object.fromEntries((readJSON(F.toponims, { toponims: [] }).toponims || []).map((t) => [t.id, t]));
  const flags = readJSON(F.flags, {});  // {id:[codes]} from quality_audit.py
  const candById = Object.fromEntries((readJSON(F.recheck, [])).map((it) => [it.id, it.candidates || []]));
  const A = (v) => (v == null || v === '') ? [] : (Array.isArray(v) ? v.slice() : [v]);  // tipus/ordre are multi-value
  return matches.map((m) => {
    const c = cur[m.id] || {};
    const g = geoById[m.id] || {};
    const tip = c.tipus != null ? A(c.tipus) : A(m.tipus), tip0 = A(m.tipus);
    const ord = c.ordre != null ? A(c.ordre) : A(m.ordre), ord0 = A(m.ordre);
    // Attach coordinates to candidates from the NGIB gazetteer (recheck stores none).
    const cands = (candById[m.id] || []).slice(0, 6).map((ca) => {
      const p = NGIB_POS.get(`${ca.grafia} ${ca.municipi}`) || NGIB_POS.get(ca.grafia);
      return { ...ca, lon: p ? p[0] : null, lat: p ? p[1] : null };
    });
    return {
      id: m.id, uid: m.id, lon: g.lon ?? null, lat: g.lat ?? null, x: g.x ?? null, y: g.y ?? null, dubte: !!g.dubte,
      flags: flags[m.id] || [],
      graf: c.graf ?? m.graf, graf0: m.graf, nom: m.nom,
      tipus: tip, tipus0: tip0, tipusEdited: c.tipus != null && tip.join('|') !== tip0.join('|'),
      ordre: ord, ordre0: ord0, ordreEdited: c.ordre != null && ord.join('|') !== ord0.join('|'),
      decision: m.decision, review: m.review || null, ngib: m.ngib || null,
      municipi: m.municipi || null, km: m.km ?? null, sim: m.sim ?? null,
      candidates: cands,
      pend: c.verdict || null, pendPick: c.ngib || null,
      grafEdited: c.graf != null && c.graf !== m.graf,
      discarded: c.verdict === 'trash',
    };
  });
}

const PAGE = `<!doctype html><meta charset=utf8><title>Curació de topònims</title>
<link rel=stylesheet href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 :root{--ink:#2b2620;--soft:#7a6f60;--line:#e4dccf;--bg:#f6f1e7}
 *{box-sizing:border-box} body{margin:0;font:15px/1.4 system-ui,sans-serif;color:var(--ink);background:var(--bg)}
 header{display:flex;gap:.8rem;align-items:center;padding:.5rem 1rem;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:500;flex-wrap:wrap}
 header b{font-size:1.05rem} .grow{flex:1} .meta{color:var(--soft);font-size:.9rem}
 select,input{padding:.3rem .5rem;border:1px solid var(--line);border-radius:6px;background:#fff;font:inherit}
 .seg{display:inline-flex;border:1px solid var(--line);border-radius:999px;overflow:hidden}
 .seg button{border:0;background:transparent;padding:.3rem .8rem;cursor:pointer;font:inherit;color:var(--soft)}
 .seg button.on{background:#2f7d4f;color:#fff}
 .badge{padding:.05rem .45rem;border-radius:999px;font-size:.76rem;font-weight:600;white-space:nowrap}
 /* mateixa paleta de decisió que el mapa i la web pública (I3) */
 .b-confirmat{background:#2e7d32;color:#fff}.b-probable{background:#3f7a8a;color:#fff}
 .b-suggerit{background:#c2702f;color:#fff}.b-posicional{background:#8a8170;color:#fff}.b-sense{background:#9a4a3a;color:#fff}
 .rev{color:#1f6b3f;font-weight:700;margin-left:.25rem;cursor:help}
 /* ---- table view ---- */
 #tablewrap{max-width:1500px;margin:1rem auto;padding:0 1rem}
 table{border-collapse:collapse;width:100%;background:#fff;border:1px solid var(--line);border-radius:8px;font-size:.92rem}
 thead th{position:sticky;top:52px;background:#faf6ee;text-align:left;padding:.45rem .55rem;border-bottom:2px solid var(--line);font-size:.78rem;text-transform:uppercase;letter-spacing:.03em;color:var(--soft);z-index:5}
 td{padding:.3rem .55rem;border-bottom:1px solid #efe8db;vertical-align:middle}
 tbody tr:hover{background:#faf7f0} tr.pend{box-shadow:inset 3px 0 0 #c0530a} tr.disc td{opacity:.45;text-decoration:line-through}
 td input.eg{width:11rem;font-weight:600} td input.en{width:12rem}
 td input.en.pendval{background:#fff3e6;border-color:#c0530a;font-weight:600}  /* pick desat, encara sense bakejar */
 .chips{display:flex;gap:.25rem;flex-wrap:wrap;margin-top:.2rem}
 .chip{font-size:.74rem;padding:.05rem .4rem;border:1px solid var(--line);border-radius:999px;background:#f6f7f1;cursor:pointer;color:#1d7a6b}
 .chip:hover{border-color:#2f7d4f;background:#eaf3ec}
 .rowact button{border:1px solid var(--line);border-radius:6px;background:#fff;cursor:pointer;font:inherit;padding:.2rem .4rem;margin-left:.15rem}
 .rowact .ok{color:#2f7d4f}.rowact .tr{color:#8a4a1d}.rowact .un{color:#3a6098}
 .num{text-align:right;font-variant-numeric:tabular-nums;color:var(--soft)}
 .pendtag{font-size:.7rem;color:#c0530a;font-weight:700}
 .lectlink{cursor:pointer;border-bottom:1px dashed var(--soft)} .lectlink:hover{color:#2f7d4f;border-bottom-color:#2f7d4f}
 .edcell,.edcellc{cursor:pointer} .edcell .celltxt,.edcellc .celltxt{border-bottom:1px dashed var(--soft)} .edcell:hover .celltxt,.edcellc:hover .celltxt{color:#2f7d4f;border-bottom-color:#2f7d4f}
 .chkpop{position:absolute;z-index:30;margin-top:.2rem;min-width:14rem;max-height:18rem;overflow:auto;background:#fff;border:1px solid #2f7d4f;border-radius:8px;box-shadow:0 6px 22px rgba(0,0,0,.22);padding:.35rem}
 .chkpop:focus{outline:none}
 .chkitems{display:flex;flex-direction:column}
 .chkpop label{display:flex;align-items:center;gap:.45rem;padding:.2rem .35rem;border-radius:5px;font-size:.9rem;white-space:nowrap;cursor:pointer}
 .chkpop label:hover{background:#eaf3ec}
 .chkbar{display:flex;gap:.4rem;margin-top:.35rem;padding-top:.35rem;border-top:1px solid var(--line)}
 .chkbar button{flex:1;border:1px solid var(--line);border-radius:6px;background:#fff;cursor:pointer;font:inherit;padding:.25rem .4rem}
 .chkbar .chkdone{color:#2f7d4f;border-color:#2f7d4f}
 td.edcell{position:relative} .edcellc{position:relative;display:inline-block}
 .warn{color:#c0530a;font-weight:700;cursor:help}
 .gcell{white-space:nowrap} .gcell .warn,.gcell .pendtag{vertical-align:middle}
 tr.disc .warn{opacity:.4}
 .selcell{width:1.6rem;text-align:center;padding-left:.4rem} tr.selrow>td{background:#eaf3ec}
 th.sortable{cursor:pointer;user-select:none} th.sortable:hover{color:#2f7d4f}
 .batchbar{position:sticky;top:52px;z-index:6;background:#fff7e8;border:1px solid #e6c87a;border-radius:8px;padding:.45rem .7rem;margin-bottom:.5rem;display:flex;gap:.4rem;align-items:center;flex-wrap:wrap}
 .batchbar button{border:1px solid var(--line);border-radius:6px;background:#fff;cursor:pointer;font:inherit;padding:.2rem .55rem;margin-left:.15rem}
 .batchbar .btr{color:#8a4a1d}.batchbar .bok{color:#2f7d4f}.batchbar .bun{color:#3a6098}
 /* ---- crop lightbox (zoom) ---- */
 #lb{position:fixed;inset:0;background:rgba(20,15,8,.92);display:none;z-index:2000;cursor:zoom-out;padding:1rem;overflow:auto}
 #lb.show{display:flex;align-items:center;justify-content:center} #lb img{max-width:96vw;max-height:96vh;border:2px solid #fdf6e8;box-shadow:0 8px 40px rgba(0,0,0,.5)}
 .crop{cursor:zoom-in}
 /* ---- geo (map) view ---- */
 #geoview{max-width:1500px;margin:1rem auto;padding:0 1rem}
 #geomap{height:78vh;border:1px solid var(--line);border-radius:8px;background:#e9e2cf}
 .geolegend{display:flex;flex-wrap:wrap;gap:.4rem 1rem;margin:.1rem 0 .6rem;font-size:.85rem;color:var(--soft)}
 .geolegend .lg{display:inline-flex;align-items:center;gap:.35rem}
 .geolegend .lg i{width:.8rem;height:.8rem;border-radius:50%;border:1px solid rgba(40,30,20,.4);display:inline-block}
 .geolegend .lg .ring{background:transparent;border:2px solid #1d6b2a}
 .geolegend .lg.sep{border-left:1px solid var(--line);padding-left:1rem}
 /* ---- card view ---- */
 main{max-width:1280px;margin:1.2rem auto;padding:0 1rem;display:grid;grid-template-columns:1.35fr 1fr;gap:1.4rem;align-items:start}
 #app{min-width:0} #map{height:80vh;position:sticky;top:64px;border:1px solid var(--line);border-radius:8px;background:#eee}
 .crop{width:100%;border:1px solid var(--line);border-radius:8px;background:#fff}
 .cand{display:block;width:100%;text-align:left;padding:.5rem .7rem;margin:.3rem 0;border:1px solid var(--line);border-radius:8px;background:#fff;cursor:pointer;font:inherit}
 .cand:hover,.cand.rec{border-color:#2f7d4f;background:#f0f7f1} .cand b{font-size:1.02rem}.cand .m{color:var(--soft);font-size:.85rem}.cand kbd{float:right;color:var(--soft)}
 .act{display:flex;gap:.5rem;margin-top:.8rem}.act button{flex:1;padding:.5rem;border:1px solid var(--line);border-radius:8px;background:#fff;cursor:pointer;font:inherit}
 .none{color:#a23}.skip{color:var(--soft)}.trash{color:#8a4a1d}.ok{color:#2f7d4f}.undo{color:#3a6098}
 .cand:active,.act button:active{transform:scale(.97)} .act button:focus-visible,.cand:focus-visible{outline:2px solid #2f7d4f;outline-offset:1px}
 .cand.sel{border-color:#2f7d4f;background:#dff0e4;box-shadow:inset 0 0 0 2px #2f7d4f;font-weight:600}
 .act button.hit{background:#dff0e4;border-color:#2f7d4f}
 #toast{position:fixed;left:50%;top:62px;transform:translateX(-50%) translateY(-8px);background:#2b2620;color:#fff;padding:.5rem .9rem;border-radius:8px;font-weight:600;box-shadow:0 4px 16px rgba(0,0,0,.25);opacity:0;pointer-events:none;transition:opacity .12s,transform .12s;z-index:1000}
 #toast.show{opacity:1;transform:translateX(-50%) translateY(0)} #toast.bad{background:#8a3a1d} #toast.warn{background:#8a4a1d}
 kbd{font:.8rem monospace;background:var(--line);border-radius:4px;padding:0 .3rem}
 .done{text-align:center;padding:3rem;color:var(--soft)} .hint{color:var(--soft);font-size:.85rem;text-align:center;margin:.6rem 0}
</style>
<header>
 <b>Curació · Mut 1683</b>
 <span class=seg><button id=mTable class=on>Taula</button><button id=mCard>Fitxes</button><button id=mGeo>Mapa</button></span>
 <input id=search placeholder="🔍 cerca grafia / nom / NGIB" style="width:16rem">
 <label class=meta>conf <select id=fdec><option value="">tota</option><option>confirmat</option><option>probable</option><option>suggerit</option><option>posicional</option><option>sense</option></select></label>
 <label class=meta>tipus <select id=ftip><option value="">tots</option></select></label>
 <label class=meta>orde <select id=ford><option value="">tots</option><option value=__any>amb orde</option><option value=__none>sense orde</option></select></label>
 <label class=meta>revisió <select id=frev><option value="">tota</option><option value=any>revisat o corregit</option><option value=revisat>només revisat</option><option value=corregit>només corregit</option><option value=none>sense revisar</option></select></label>
 <label class=meta>⚠ <select id=fprob><option value="">tots</option><option value=prob>amb problemes</option><option value=ok>sense problemes</option></select></label>
 <span class=grow></span>
 <span id=prog class=meta></span>
</header>
<div id=tablewrap></div>
<main id=cardview style=display:none><div id=app></div><div id=map></div></main>
<div id=geoview style=display:none><div class=geolegend id=geolegend></div><div id=geomap></div></div>
<div class=hint id=hint></div>
<div id=lb><img alt="recorte ampliat"></div>
<div id=toast></div>
<script>
var MODE='table', ROWS=[], NGIB=[];
var SORT={key:'',dir:1}, SEL={};   // SEL = id->1 (multiselecció de la taula)
var ROWSLOADED=false;              // ROWS ja carregades (evita re-fetch en canviar de vista)
var ROWSDIRTY=false;               // un canvi des de Fitxes/Geo invalida la cache de la Taula
var UNDO=[], PENDTIP=null;         // pila de desfer de la taula; valor de filtre tipus pendent de restaurar
var DECORD={confirmat:5,probable:4,suggerit:3,posicional:2,sense:1};
// Columnes ordenables de la taula (clau del model + etiqueta).
var COLS=[{k:'graf',t:'Grafia (gravat)'},{k:'nom',t:'Lectura'},{k:'tipus',t:'Tipus'},{k:'ordre',t:'Ordre'},
  {k:'decision',t:'Confiança'},{k:'ngib',t:'NGIB'},{k:'municipi',t:'Municipi'},{k:'km',t:'km',cls:'num'}];
// Categories LITERALS de la llegenda del gravat (1785), tal com hi estan gravades.
// The 8 place classes of the Mut 1683 legend ("Notarū Explicatio") + "altre".
var TIPS=['Bisbat','Abadia','Vila parroquial','Llogaret','Castell',"Casa d'estudis",
  'Torre de guaita','Torre de senyals','Ciutat','altre'];
// The Mut legend has no religious-order axis (that was despuig's 1785 map).
var ORDRES=[];
function tipSel(id,cur){var opts=TIPS.slice();if(cur&&opts.indexOf(cur)<0)opts.unshift(cur);return '<select class=etip data-id="'+id+'">'+opts.map(function(x){return '<option'+(x===cur?' selected':'')+'>'+esc(x)+'</option>';}).join('')+'</select>';}
function ordSel(id,cur){var opts=ORDRES.slice();if(cur&&opts.indexOf(cur)<0)opts.unshift(cur);return '<select class=eord data-id="'+id+'"><option value=""'+(cur?'':' selected')+'>—</option>'+opts.map(function(x){return '<option'+(x===cur?' selected':'')+'>'+esc(x)+'</option>';}).join('')+'</select>';}
var esc=function(s){return (s==null?'':''+s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});};
// Etiquetes humanes dels flags de qualitat (quality_audit.py).
var FLAGLAB={empty:'buit',very_short:'molt curt',short_single:'token curt',lower_start:'minúscula inicial',dangling_edge:'vora penjant',has_digit:'dígits',odd_char:'caràcters/abreviatura',ngib_far:'NGIB llunyà (compartit entre fulls)',dup_near:'possible duplicat (mateix nom a prop)'};
function flagTxt(fs){return (fs||[]).map(function(f){return FLAGLAB[f]||f;}).join(', ');}
// tipus i ordre són multivalor: normalitza a llista i mostra unit amb " · ".
function arr(v){ return v==null||v===''?[]:(Array.isArray(v)?v.slice():[v]); }
function tjoin(v){ return arr(v).join(' · '); }
var $=function(s){return document.querySelector(s);};
// Lightbox per ampliar el recorte del gravat (vista Fitxes).
function openLightbox(src){var lb=$('#lb');lb.querySelector('img').src=src;lb.classList.add('show');}
function closeLightbox(){var lb=$('#lb');lb.classList.remove('show');lb.querySelector('img').src='';}
// Persistència de l'estat de la UI (full, vista, filtres, ordre) entre recàrregues (B4).
function saveUI(){ try{ localStorage.setItem('curUI',JSON.stringify({mode:MODE,sort:SORT,f:{s:$('#search').value,d:$('#fdec').value,t:$('#ftip').value,o:$('#ford').value,r:$('#frev').value,p:$('#fprob').value}})); }catch(e){} }
function loadUI(){ try{ return JSON.parse(localStorage.getItem('curUI')||'null'); }catch(e){ return null; } }

function api(p){ return p; }   // single sheet: no ?q= param
// Returns true only if the server confirmed the save. Callers MUST check it before
// updating the UI optimistically, so a failed write never looks like a success.
async function post(body){
  try{ var r=await fetch('/pick',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok){ toast('⚠ NO desat — error '+r.status,'bad'); return false; }
    var j=await r.json(); if(!j||!j.ok){ toast('⚠ El servidor no ha desat','bad'); return false; }
    if(MODE!=='table') ROWSDIRTY=true;   // edició feta fora de la Taula: cal refrescar-la en tornar-hi
    return true;
  }catch(e){ toast('⚠ Sense connexió amb el servidor — NO desat','bad'); return false; }
}

async function boot(){
  $('#mTable').onclick=function(){setMode('table');};
  $('#mCard').onclick=function(){setMode('card');};
  $('#mGeo').onclick=function(){setMode('geo');};
  $('#ford').innerHTML+=ORDRES.map(function(x){return '<option>'+esc(x)+'</option>';}).join('');  // afegeix les ordes al filtre
  ['#fdec','#ftip','#ford','#frev','#fprob'].forEach(function(s){$(s).addEventListener('input',onFilter);});
  var _ft; $('#search').addEventListener('input',function(){ clearTimeout(_ft); _ft=setTimeout(onFilter,160); });  // debounce mentre s'escriu
  $('#lb').onclick=closeLightbox;
  addEventListener('keydown',function(e){ if(e.key==='Escape'&&$('#lb').classList.contains('show')){closeLightbox();} });
  // Ctrl/Cmd+Z desfà l'última acció (taula o fitxes) (I2/B1).
  addEventListener('keydown',function(e){ if((e.ctrlKey||e.metaKey)&&(e.key==='z'||e.key==='Z')){ if(MODE==='table'){e.preventDefault();tableUndo();} else if(MODE==='card'){e.preventDefault();cundo();} } });
  try{ NGIB=await (await fetch('/ngib')).json(); }catch(e){}
  // Restaura l'estat de la UI desat (B4).
  var ui=loadUI();
  if(ui){
    if(ui.f){ $('#search').value=ui.f.s||''; $('#fdec').value=ui.f.d||''; $('#ford').value=ui.f.o||''; $('#frev').value=ui.f.r||''; $('#fprob').value=ui.f.p||''; PENDTIP=ui.f.t||null; }
    if(ui.sort) SORT=ui.sort;
    if(ui.mode) MODE=ui.mode;
  }
  setMode(MODE);
}
function setMode(m){ MODE=m;
  $('#mTable').classList.toggle('on',m==='table'); $('#mCard').classList.toggle('on',m==='card'); $('#mGeo').classList.toggle('on',m==='geo');
  $('#tablewrap').style.display=m==='table'?'':'none'; $('#cardview').style.display=m==='card'?'grid':'none'; $('#geoview').style.display=m==='geo'?'':'none'; saveUI(); reload(); }
function reload(){ if(MODE==='table') loadTable(); else if(MODE==='geo') loadGeo(); else loadCards(); }
function onFilter(){ saveUI(); if(MODE==='table') applyFilter(); else if(MODE==='geo') renderGeo(); else cbuild(); }

/* ================= TABLE VIEW ================= */
// Fetch the rows only when the loaded sheet differs from the current one; views share ROWS.
async function ensureRows(force){ if(!force && !ROWSDIRTY && ROWSLOADED && ROWS.length)return; ROWS=(await (await fetch(api('/table'))).json()).rows; ROWSLOADED=true; ROWSDIRTY=false; SEL={}; UNDO=[]; }
async function loadTable(){
  await ensureRows();
  fillTipFilter();
  buildTable();
  $('#hint').innerHTML='Clica una capçalera per ordenar · marca files (☑) per a accions en lot · edita la lectura (Enter o sortint del camp desa) · tria/escriu el NGIB (Enter), buida\\'l per «cap match», o clica un candidat · ✓ correcte · 🗑 brossa · ↶ o <kbd>Ctrl+Z</kbd> desfés.';
}
function sortRows(){ if(!SORT.key)return; var k=SORT.key,d=SORT.dir;
  ROWS.sort(function(a,b){ var x,y;
    if(k==='km'){x=a.km==null?Infinity:a.km;y=b.km==null?Infinity:b.km;}
    else if(k==='decision'){x=DECORD[a.decision]||0;y=DECORD[b.decision]||0;}
    else if(k==='tipus'||k==='ordre'){x=tjoin(a[k]).toLowerCase();y=tjoin(b[k]).toLowerCase();}
    else{x=(''+(a[k]||'')).toLowerCase();y=(''+(b[k]||'')).toLowerCase();}
    return x<y?-d:x>y?d:0; });
}
function buildTable(){ sortRows();
  var head='<tr><th class=selcell><input type=checkbox id=selall title="selecciona el que es mostra"></th>'
    +COLS.map(function(c){var ar=SORT.key===c.k?(SORT.dir>0?' ▲':' ▼'):'';return '<th class="sortable'+(c.cls?' '+c.cls:'')+'" data-key="'+c.k+'">'+c.t+ar+'</th>';}).join('')
    +'<th></th></tr>';
  var body=ROWS.map(rowHTML).join('');
  $('#tablewrap').innerHTML='<div id=batchbar class=batchbar style=display:none></div><table><thead>'+head+'</thead><tbody id=tb>'+body+'</tbody></table>';
  wireTable(); wireHead(); applyFilter(); prog(); updateBatchBar();
}
function wireHead(){
  document.querySelectorAll('#tablewrap th.sortable').forEach(function(th){th.onclick=function(){
    var k=th.dataset.key; if(SORT.key===k)SORT.dir=-SORT.dir; else{SORT.key=k;SORT.dir=1;} buildTable();
  };});
  var sa=$('#selall'); if(sa)sa.onchange=function(){toggleSelAll(sa.checked);};
}
function rowHTML(r){
  var u=r.uid||r.id;
  var fs=r.flags||[];
  // El pick encara no s'ha bakejat (r.ngib ve de matches.json), així que mostra el
  // pick PENDENT a la columna NGIB; si s'ha marcat «cap match», buida-la. Sense això,
  // un pick desat (fitxa o taula) quedava invisible fins a re-bakejar el full.
  var ngibVal=r.pend==='pick'?(r.pendPick||''):(r.pend==='none'?'':(r.ngib||''));
  var warn=fs.length?' <span class=warn title="'+esc(flagTxt(fs))+'">⚠</span>':'';
  var pend=r.pend?'<span class=pendtag> ·'+r.pend+(r.pendPick?' '+esc(r.pendPick):'')+'</span>':'';
  var rev=r.review==='revisat'?'<span class=rev title="revisat a mà">✓</span>':r.review==='corregit'?'<span class=rev title="corregit a mà">✎</span>':'';
  var chips='';  // els candidats (r.candidates) es trien a la fitxa; la taula es manté neta per a escaneig
  return '<tr data-id="'+esc(u)+'" data-dec="'+r.decision+'" data-tip="|'+esc(arr(r.tipus).join('|'))+'|" data-ord="|'+esc(arr(r.ordre).join('|'))+'|" data-rev="'+(r.review||'')+'" data-prob="'+(fs.length?'1':'')+'" '
    +'data-text="'+esc(((r.graf||'')+' '+(r.nom||'')+' '+(r.ngib||'')+' '+(r.pendPick||'')+' '+(r.municipi||'')).toLowerCase())+'"'
    +' class="'+(r.pend?'pend ':'')+(r.discarded?'disc ':'')+(SEL[u]?'selrow':'')+'">'
    +'<td class=selcell><input type=checkbox class=selbox data-id="'+esc(u)+'"'+(SEL[u]?' checked':'')+'></td>'
    +'<td class=gcell><input class=eg data-id="'+esc(u)+'" value="'+esc(r.graf)+'">'+warn+(r.grafEdited?' <span class=pendtag>✎</span>':'')+'</td>'
    +'<td><span class=lectlink data-openid="'+esc(u)+'" title="obre la fitxa d\\'edició">'+esc(r.nom)+'</span></td>'
    +'<td class=edcell data-edit=tip data-id="'+esc(u)+'"><span class=celltxt>'+esc(tjoin(r.tipus)||'—')+'</span>'+(r.tipusEdited?' <span class=pendtag>✎</span>':'')+'</td>'
    +'<td class=edcell data-edit=ord data-id="'+esc(u)+'"><span class=celltxt>'+esc(tjoin(r.ordre)||'—')+'</span>'+(r.ordreEdited?' <span class=pendtag>✎</span>':'')+'</td>'
    +'<td><span class="badge b-'+r.decision+'">'+r.decision+'</span>'+rev+pend+'</td>'
    +'<td><input class="en'+(r.pend==='pick'?' pendval':'')+'" data-id="'+esc(u)+'" value="'+esc(ngibVal)+'" placeholder="—">'+(chips?'<div class=chips>'+chips+'</div>':'')+'</td>'
    +'<td class=meta>'+esc(r.municipi||'')+'</td><td class=num>'+(r.km==null?'':r.km)+'</td>'
    +'<td class=rowact><button class=ok title="correcte (revisat)">✓</button><button class=tr title="brossa">🗑</button><button class=un title="desfés">↶</button></td>'
    +'</tr>';
}
function wireTable(){
  var tb=$('#tb');
  tb.addEventListener('keydown',function(e){
    if(e.key!=='Enter')return; var t=e.target;
    if(t.classList.contains('eg')){ saveReading(t.dataset.id,t.value); }
    else if(t.classList.contains('en')){ if(t.value.trim()) pickRow(t.dataset.id,t.value.trim()); else noneRow(t.dataset.id); }
  });
  tb.addEventListener('click',function(e){
    if(e.target.classList.contains('lectlink')){ openCardFor(e.target.dataset.openid); return; }
    var ed=e.target.closest('.edcell');
    if(ed && !ed.querySelector('.chkpop')){
      var euid=ed.dataset.id, er=rowOf(euid); if(!er)return; var which=ed.dataset.edit;
      openChecklist(ed, which==='tip'?TIPS:ORDRES, which==='tip'?arr(er.tipus):arr(er.ordre),
        function(vals){ if(which==='tip') setTipusM(euid,vals); else setOrdreM(euid,vals); },
        function(){ refreshRow(euid); });
      return;
    }
    if(ed){ return; }                          // clicks inside the open checklist
    var tr=e.target.closest('tr'); if(!tr)return; var id=tr.dataset.id;
    if(e.target.classList.contains('chip')){ var g=e.target.dataset.g; var en=tr.querySelector('.en'); if(en)en.value=g; pickRow(id,g); }
    else if(e.target.classList.contains('ok')) okRow(id);
    else if(e.target.classList.contains('tr')) trashRow(id);
    else if(e.target.classList.contains('un')) undoRow(id);
  });
  tb.addEventListener('change',function(e){
    if(e.target.classList.contains('selbox')){ var u=e.target.dataset.id; if(e.target.checked)SEL[u]=1; else delete SEL[u]; var tr=e.target.closest('tr'); if(tr)tr.classList.toggle('selrow',e.target.checked); updateBatchBar(); }
  });
  // Desa la lectura en sortir del camp (no només amb Enter): evita perdre edicions.
  tb.addEventListener('focusout',function(e){ if(e.target.classList&&e.target.classList.contains('eg')) saveReading(e.target.dataset.id,e.target.value); });
}
// Multi-select checklist, mounted lazily into a cell (table or card). tipus/ordre are
// multi-value, so a checklist (not a single <select>); also keeps the table light
// (no thousands of <option> nodes — the picker exists only while editing one cell).
var CHK=null;
function openChecklist(anchor, vocab, current, onSave, onCancel){
  if(CHK) CHK.close(false);
  anchor.innerHTML='<div class=chkpop tabindex=-1><div class=chkitems>'
    +vocab.map(function(x){return '<label><input type=checkbox value="'+esc(x)+'"'+(current.indexOf(x)>=0?' checked':'')+'> '+esc(x)+'</label>';}).join('')
    +'</div><div class=chkbar><button type=button class=chkdone>✓ Desa</button><button type=button class=chkcancel>× cancel·la</button></div></div>';
  var pop=anchor.querySelector('.chkpop'), done=false;
  function vals(){ return [].slice.call(pop.querySelectorAll('input:checked')).map(function(i){return i.value;}); }
  function close(save){ if(done)return; done=true; document.removeEventListener('mousedown',outside,true); CHK=null; if(save)onSave(vals()); else onCancel(); }
  function outside(ev){ if(!anchor.contains(ev.target)) close(true); }
  pop.querySelector('.chkdone').onclick=function(){close(true);};
  pop.querySelector('.chkcancel').onclick=function(){close(false);};
  pop.addEventListener('keydown',function(e){ if(e.key==='Escape'){e.preventDefault();close(false);} });
  CHK={close:close};
  setTimeout(function(){ document.addEventListener('mousedown',outside,true); },0);
  pop.focus();
}
function selVisible(){ var out=[]; document.querySelectorAll('#tb tr').forEach(function(tr){ if(tr.style.display!=='none')out.push(tr.dataset.id); }); return out; }
function toggleSelAll(on){ selVisible().forEach(function(u){ if(on)SEL[u]=1; else delete SEL[u]; });
  document.querySelectorAll('#tb tr').forEach(function(tr){ if(tr.style.display==='none')return; var cb=tr.querySelector('.selbox'); if(cb)cb.checked=on; tr.classList.toggle('selrow',on); });
  updateBatchBar();
}
function updateBatchBar(){ var bar=$('#batchbar'); if(!bar)return; var n=Object.keys(SEL).length;
  if(!n){ bar.style.display='none'; bar.innerHTML=''; return; }
  bar.style.display='';
  bar.innerHTML='<b>'+n+' seleccionats</b> · accions en lot: '
    +'<button class=bok>✓ Correcte</button><button class=btr>🗑 Brossa</button><button class=bun>↶ Desfés</button>'
    +' · tipus <select class=btip><option value="">—</option>'+TIPS.map(function(x){return '<option>'+esc(x)+'</option>';}).join('')+'</select>'
    +' · orde <select class=bord><option value="">—</option><option value="__clear">(cap orde)</option>'+ORDRES.map(function(x){return '<option>'+esc(x)+'</option>';}).join('')+'</select>'
    +' <button class=bclr>✕ deselecciona</button>';
  bar.querySelector('.bok').onclick=function(){batchVerdict('ok');};
  bar.querySelector('.btr').onclick=function(){batchVerdict('trash');};
  bar.querySelector('.bun').onclick=function(){batchVerdict('undo');};
  bar.querySelector('.bclr').onclick=function(){SEL={};buildTable();};
  bar.querySelector('.btip').onchange=function(){batchTipus(this.value);};
  bar.querySelector('.bord').onchange=function(){batchOrdre(this.value);};
}
async function batchVerdict(action){ var ids=Object.keys(SEL); if(!ids.length)return; var n=0,undos=[];
  for(var i=0;i<ids.length;i++){ var r=rowOf(ids[i]); if(!r)continue; var p=snap(r);
    if(!await post({id:r.id,action:action})){ toast('⚠ Aturat a '+r.id+' ('+n+' fets)','bad'); break; }
    if(action==='ok'){r.pend='ok';r.review='revisat';}
    else if(action==='trash'){r.pend='trash';r.discarded=true;}
    else if(action==='undo'){r.pend=null;r.pendPick=null;r.discarded=false;}
    undos.push(restorer(ids[i],p)); n++;
  }
  if(undos.length)pushUndo(async function(){ for(var j=0;j<undos.length;j++)await undos[j](); buildTable(); });
  buildTable(); prog(); toast('✓ '+n+' fila'+(n===1?'':'s'));
}
async function batchTipus(v){ if(!v)return; var vals=[v]; var ids=Object.keys(SEL),n=0,undos=[];
  for(var i=0;i<ids.length;i++){ var r=rowOf(ids[i]); if(!r)continue; var p=snap(r);
    if(!await post({id:r.id,action:'tipus',tipus:vals})){ toast('⚠ Aturat a '+r.id,'bad'); break; }
    r.tipus=vals; r.tipusEdited=(vals.join('|')!==arr(r.tipus0).join('|')); undos.push(restorer(ids[i],p)); n++;
  }
  if(undos.length)pushUndo(async function(){ for(var j=0;j<undos.length;j++)await undos[j](); buildTable(); });
  buildTable(); toast('🏷 '+v+' ×'+n);
}
async function batchOrdre(v){ if(!v)return; var vals=(v==='__clear')?[]:[v]; var ids=Object.keys(SEL),n=0,undos=[];
  for(var i=0;i<ids.length;i++){ var r=rowOf(ids[i]); if(!r)continue; var p=snap(r);
    if(!await post({id:r.id,action:'ordre',ordre:vals})){ toast('⚠ Aturat a '+r.id,'bad'); break; }
    r.ordre=vals; r.ordreEdited=(vals.join('|')!==arr(r.ordre0).join('|')); undos.push(restorer(ids[i],p)); n++;
  }
  if(undos.length)pushUndo(async function(){ for(var j=0;j<undos.length;j++)await undos[j](); buildTable(); });
  buildTable(); toast((vals.length?'⛪ '+v:'⛪ (cap orde)')+' ×'+n);
}
function rowOf(uid){ return ROWS.find(function(r){return (r.uid||r.id)===uid;}); }
function trEl(uid){ return $('#tb tr[data-id="'+CSS.escape(uid)+'"]'); }
// ---- unified undo stack (verdict + graf + tipus) ----
function snap(r){ return {pend:r.pend,pendPick:r.pendPick,review:r.review,discarded:r.discarded,graf:r.graf,grafEdited:r.grafEdited,tipus:r.tipus,tipusEdited:r.tipusEdited,ordre:r.ordre,ordreEdited:r.ordreEdited}; }
function pushUndo(fn){ UNDO.push(fn); if(UNDO.length>100)UNDO.shift(); }
// Restorer: re-applies a full prior row state (verdict + reading + tipus) with minimal posts.
function restorer(uid,p){ return async function(){ var r=rowOf(uid); if(!r)return;
  var body={id:r.id};
  if(!p.pend)body.action='undo'; else if(p.pend==='pick'){body.action='pick';body.grafia=p.pendPick||'';} else body.action=p.pend;
  if(p.grafEdited)body.graf=p.graf;                                  // restore the reading edit (rides along)
  if(!await post(body))return;
  if(!p.grafEdited && r.grafEdited) await post({id:r.id,action:'graf',graf:''});   // was unedited -> clear
  if(arr(p.tipus).join('|')!==arr(r.tipus).join('|')) await post({id:r.id,action:'tipus',tipus:arr(p.tipus)});
  if(arr(p.ordre).join('|')!==arr(r.ordre).join('|')) await post({id:r.id,action:'ordre',ordre:arr(p.ordre)});
  r.pend=p.pend;r.pendPick=p.pendPick;r.review=p.review;r.discarded=p.discarded;r.graf=p.graf;r.grafEdited=p.grafEdited;r.tipus=p.tipus;r.tipusEdited=p.tipusEdited;r.ordre=p.ordre;r.ordreEdited=p.ordreEdited;
  refreshRow(uid); prog(); }; }
async function tableUndo(){ var fn=UNDO.pop(); if(!fn){toast('(res a desfer)','warn');return;} await fn(); toast('↶ Desfet'); }
async function setTipusM(uid,vals){ var r=rowOf(uid); if(!r){return;} vals=vals||[];
  if(vals.join('|')!==arr(r.tipus).join('|')){ var p=snap(r);
    if(!await post({id:r.id,action:'tipus',tipus:vals})){ refreshRow(uid); return; }
    r.tipus=vals; r.tipusEdited=(vals.join('|')!==arr(r.tipus0).join('|')); pushUndo(restorer(uid,p)); toast(vals.length?'🏷 '+vals.join(' · '):'🏷 (cap tipus)'); }
  refreshRow(uid);
}
async function setOrdreM(uid,vals){ var r=rowOf(uid); if(!r){return;} vals=vals||[];
  if(vals.join('|')!==arr(r.ordre).join('|')){ var p=snap(r);
    if(!await post({id:r.id,action:'ordre',ordre:vals})){ refreshRow(uid); return; }
    r.ordre=vals; r.ordreEdited=(vals.join('|')!==arr(r.ordre0).join('|')); pushUndo(restorer(uid,p)); toast(vals.length?'⛪ '+vals.join(' · '):'⛪ (cap orde)'); }
  refreshRow(uid);
}
async function saveReading(uid,v){ var r=rowOf(uid); v=(v||'').trim(); if(!r||!v||v===r.graf)return; var p=snap(r); if(!await post({id:r.id,action:'graf',graf:v}))return; r.graf=v; r.grafEdited=(v!==r.graf0); flash(uid); refreshRow(uid); pushUndo(restorer(uid,p)); toast('💾 Lectura desada'); }
async function pickRow(uid,g){ var r=rowOf(uid); if(!r)return; var p=snap(r); if(!await post({id:r.id,action:'pick',grafia:g,graf:ged(uid)}))return; r.pend='pick'; r.pendPick=g; r.review=(g===r.ngib?'revisat':'corregit'); refreshRow(uid); prog(); pushUndo(restorer(uid,p)); toast('✓ '+g); }
async function noneRow(uid){ var r=rowOf(uid); if(!r)return; var p=snap(r); if(!await post({id:r.id,action:'none',graf:ged(uid)}))return; r.pend='none'; r.pendPick=null; r.ngib=null; r.review=null; refreshRow(uid); prog(); pushUndo(restorer(uid,p)); toast('Cap match','warn'); }
async function okRow(uid){ var r=rowOf(uid); if(!r)return; var p=snap(r); if(!await post({id:r.id,action:'ok',graf:ged(uid)}))return; r.pend='ok'; r.review='revisat'; refreshRow(uid); prog(); pushUndo(restorer(uid,p)); toast('✓ Correcte'); }
async function trashRow(uid){ var r=rowOf(uid); if(!r)return; var p=snap(r); if(!await post({id:r.id,action:'trash',graf:ged(uid)}))return; r.pend='trash'; r.discarded=true; refreshRow(uid); prog(); pushUndo(restorer(uid,p)); toast('🗑 Brossa','bad'); }
async function undoRow(uid){ var r=rowOf(uid); if(!r)return; var p=snap(r); if(!await post({id:r.id,action:'undo'}))return; r.pend=null; r.pendPick=null; r.discarded=false; refreshRow(uid); prog(); pushUndo(restorer(uid,p)); toast('↶ Desfet'); }
// Read the LIVE grafia <input> (not the stale row model) so an edit typed without Enter
// still rides along ✓/🗑/pick; sync the model so ✎ shows after the row refresh.
function ged(uid){ var tr=trEl(uid),r=rowOf(uid); if(!r)return null; var inp=tr&&tr.querySelector('.eg'); var v=inp?inp.value.trim():''; if(v&&v!==r.graf)r.graf=v; r.grafEdited=(r.graf!==r.graf0); return r.grafEdited?r.graf:null; }
function refreshRow(uid){ var tr=trEl(uid); if(!tr)return; var r=rowOf(uid); var n=document.createElement('tbody'); n.innerHTML=rowHTML(r); tr.replaceWith(n.firstChild); applyFilter(); }
function flash(id){ var tr=trEl(id); if(tr){tr.style.background='#eaf3ec';setTimeout(function(){tr.style.background='';},500);} }
function fillTipFilter(){
  var sel=$('#ftip'); if(!sel)return; var cur=sel.value;
  var present={}; ROWS.forEach(function(r){arr(r.tipus).forEach(function(x){present[x]=1;});});
  // ordre: les categories de la llegenda primer (TIPS), després qualsevol altra present
  var ordered=TIPS.filter(function(x){return present[x];})
    .concat(Object.keys(present).filter(function(x){return TIPS.indexOf(x)<0;}).sort());
  if(PENDTIP!=null){ cur=PENDTIP; PENDTIP=null; }   // restaura el filtre desat (B4)
  sel.innerHTML='<option value="">tots</option>'+ordered.map(function(x){return '<option'+(x===cur?' selected':'')+'>'+esc(x)+'</option>';}).join('');
}
function applyFilter(){
  if(MODE!=='table')return; var t=($('#search').value||'').trim().toLowerCase(),d=$('#fdec').value,tp=$('#ftip').value,fo=$('#ford').value,rv=$('#frev').value,fp=$('#fprob').value;
  var rows=document.querySelectorAll('#tb tr'),shown=0;
  rows.forEach(function(tr){
    var rev=tr.dataset.rev, prob=tr.dataset.prob==='1', ord=tr.dataset.ord, hasord=ord!=='||';
    var rok=!rv||(rv==='any'?!!rev:rv==='none'?!rev:rev===rv);
    var pok=!fp||(fp==='prob'?prob:!prob);
    var ook=!fo||(fo==='__any'?hasord:fo==='__none'?!hasord:ord.indexOf('|'+fo+'|')>=0);
    var ok=(!d||tr.dataset.dec===d)&&(!tp||tr.dataset.tip.indexOf('|'+tp+'|')>=0)&&ook&&rok&&pok&&(!t||tr.dataset.text.indexOf(t)>=0);
    tr.style.display=ok?'':'none'; if(ok)shown++;
  });
  prog(shown);
}
function prog(shown){
  var done=ROWS.filter(function(r){return r.pend||r.review;}).length;
  var disc=ROWS.filter(function(r){return r.discarded;}).length;
  $('#prog').textContent=ROWS.length+' topònims · '+done+' revisats'+(disc?' · '+disc+' descartats':'')+(shown!=null?' · mostrant '+shown:'');
  saveUI();
}

/* ================= GEO (MAP) VIEW ================= */
/* Mapa geogràfic de tots els topònims, com la pestanya "Mapa" de la web pública:
   marcadors per lon/lat colorejats per decisió, mateixos filtres, clic → fitxa. */
var GEOC={confirmat:'#2e7d32',probable:'#3f7a8a',suggerit:'#c2702f',posicional:'#8a8170',sense:'#9a4a3a'};
var GEOLAB={confirmat:'Confirmat',probable:'Probable',suggerit:'Suggerit',posicional:'Posicional',sense:'Sense'};
var geomap,geolayer;
async function loadGeo(){
  await ensureRows();
  fillTipFilter();
  var present={}; ROWS.forEach(function(r){present[r.decision]=1;});
  var order=['confirmat','probable','suggerit','posicional','sense'].filter(function(d){return present[d];});
  $('#geolegend').innerHTML=order.map(function(d){return '<span class=lg><i style="background:'+GEOC[d]+'"></i>'+GEOLAB[d]+'</span>';}).join('')
    +'<span class="lg sep"><i class=ring></i>validat a mà</span>';
  initGeoMap(); renderGeo();
}
function initGeoMap(){
  if(geomap){setTimeout(function(){geomap.invalidateSize();},60);return;}
  geomap=L.map('geomap',{preferCanvas:true}).setView([39.62,2.98],10);
  var osm=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'});
  var sat=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{maxZoom:19,attribution:'Esri'});
  osm.addTo(geomap); L.control.layers({'Mapa':osm,'Satèl·lit':sat}).addTo(geomap);
  geolayer=L.layerGroup().addTo(geomap);
  geomap.on('popupopen',function(e){ var nd=e.popup._contentNode; if(!nd)return;
    var a=nd.querySelector('a[data-open]'); if(a)a.onclick=function(ev){ev.preventDefault();openCardFor(a.getAttribute('data-open'));};
    var b=nd.querySelector('a[data-table]'); if(b)b.onclick=function(ev){ev.preventDefault();gotoTableRow(b.getAttribute('data-table'));}; });
  setTimeout(function(){geomap.invalidateSize();},60);
}
function renderGeo(){
  if(!geolayer)return; geolayer.clearLayers();
  var t=($('#search').value||'').trim().toLowerCase(),d=$('#fdec').value,tp=$('#ftip').value,fo=$('#ford').value,rv=$('#frev').value,fp=$('#fprob').value,shown=0;
  ROWS.forEach(function(r){
    if(r.lat==null||r.lon==null||r.discarded)return;
    var rev=r.review||'',prob=(r.flags&&r.flags.length)>0,oa=arr(r.ordre);
    var rok=!rv||(rv==='any'?!!rev:rv==='none'?!rev:rev===rv);
    var pok=!fp||(fp==='prob'?prob:!prob);
    var ook=!fo||(fo==='__any'?oa.length>0:fo==='__none'?oa.length===0:oa.indexOf(fo)>=0);
    var ok=(!d||r.decision===d)&&(!tp||arr(r.tipus).indexOf(tp)>=0)&&ook&&rok&&pok&&(!t||((r.graf||'')+' '+(r.nom||'')+' '+(r.ngib||'')+' '+(r.municipi||'')).toLowerCase().indexOf(t)>=0);
    if(!ok)return;
    var mk=L.circleMarker([r.lat,r.lon],{radius:prob?5:4,weight:(prob||rev)?2:1,color:prob?'#c0530a':(rev?'#1d6b2a':'rgba(40,30,20,.55)'),fillColor:GEOC[r.decision]||'#888',fillOpacity:.9});
    var revTxt=rev==='corregit'?' · ✎ corregit':rev?' · ✓ revisat':'';
    mk.bindPopup('<b>'+esc(r.graf)+'</b>'+(r.nom&&r.nom!==r.graf?' <span style="opacity:.7">('+esc(r.nom)+')</span>':'')
      +(prob?'<br><span style="color:#c0530a">⚠ '+esc(flagTxt(r.flags))+'</span>':'')
      +'<br>'+(r.ngib?'NGIB: '+esc(r.ngib)+(r.municipi?' · '+esc(r.municipi):''):'<em>sense forma NGIB</em>')
      +(revTxt?'<br><span style="opacity:.7">'+revTxt.replace(/^[^a-z✎✓]*/,'')+'</span>':'')
      +'<br><a href="#" data-open="'+esc(r.uid)+'">obre la fitxa →</a> · <a href="#" data-table="'+esc(r.uid)+'">a la taula →</a>');
    mk.addTo(geolayer); shown++;
  });
  prog(shown);
}
// Salta de l'enllaç del mapa a la fila corresponent de la taula i la ressalta (I4).
function gotoTableRow(uid){
  setMode('table');
  var tries=0; (function find(){ var tr=trEl(uid);
    if(tr){ if(tr.style.display==='none'){toast('La fila està filtrada','warn');return;} tr.scrollIntoView({block:'center',behavior:'smooth'}); flash(uid); }
    else if(++tries<40) setTimeout(find,50); })();
}

/* ================= CARD VIEW (crops + map) — same canonical records as the table ================= */
var DATA=[],queue=[],ci=0,map,mlayer,ngibLayer,searchLayer,chist=[],TARGET=null;
function dById(id){for(var i=0;i<DATA.length;i++)if(DATA[i].id===id)return DATA[i];return null;}
function effNgib(d){return d.pend==='pick'?(d.pendPick||''):(d.ngib||'');}  // pick pendent o match bakejat
// Obre la vista Fitxes centrada en una entrada concreta (des de la taula/mapa).
function openCardFor(uid){
  TARGET=uid;
  setMode('card');
}
async function loadCards(){
  DATA=((await (await fetch(api('/data'))).json()).items)||[];
  initMap(); cbuild();
  $('#hint').innerHTML='Fitxes: <kbd>1</kbd>–<kbd>6</kbd> candidat · <kbd>C</kbd> correcte · <kbd>0</kbd> cap match · <kbd>D</kbd> brossa · <kbd>S</kbd> saltar · <kbd>U</kbd>/<kbd>Ctrl+Z</kbd> desfés · clica el recorte per ampliar';
}
function cbuild(){
  var t=($('#search').value||'').trim().toLowerCase(), f=$('#fdec').value, tp=$('#ftip').value, fo=$('#ford').value, fp=$('#fprob').value;
  queue=DATA.filter(function(d){
    if(d.pend) return false;                             // la cua = encara no revisats (sense verdict)
    if(f && d.decision!==f) return false;
    if(tp && arr(d.tipus).indexOf(tp)<0) return false;
    if(fo){ var oa=arr(d.ordre); if(fo==='__any'?!oa.length:fo==='__none'?!!oa.length:oa.indexOf(fo)<0) return false; }
    if(fp){ var prob=(d.flags&&d.flags.length)>0; if(fp==='prob'?!prob:prob) return false; }
    if(t){ var hay=((d.graf||'')+' '+(d.nom||'')+' '+effNgib(d)+' '+(d.municipi||'')).toLowerCase(); if(hay.indexOf(t)<0) return false; }
    return true;
  });
  ci=0;
  if(TARGET){
    var idx=queue.map(function(d){return d.id;}).indexOf(TARGET);
    if(idx<0){ var it=dById(TARGET); if(it){ queue.unshift(it); idx=0; } }  // ja revisat/filtrat: l'injectem
    if(idx>=0) ci=idx;
    TARGET=null;
  }
  crender();
}
function crender(){
  var done=DATA.filter(function(d){return d.pend;}).length;
  $('#prog').textContent='fitxes · revisats '+done+'/'+DATA.length+' · cua '+queue.length;
  var app=$('#app');
  if(!DATA.length){app.innerHTML='<div class=done>No hi ha crops rendetjats a data/toponims/review-crops/.<br>Usa la vista Taula o la vista Mapa.</div>';return;}
  if(!queue.length){app.innerHTML='<div class=done>✓ Res més a la cua amb aquest filtre.</div>';clearMap();return;}
  var d=queue[ci];
  var eng=effNgib(d);
  var cands=(d.candidates||[]).map(function(c,n){var rec=(c.grafia===eng)?' rec':'';return '<button class="cand'+rec+'" data-g="'+esc(c.grafia)+'"><kbd>'+(n+1)+'</kbd><b>'+esc(c.grafia)+'</b><div class=m>'+esc(c.municipi||'?')+' · '+c.km+'km · sim '+c.sim+'</div></button>';}).join('');
  var etip=arr(d.tipus);
  var eord=arr(d.ordre);
  app.innerHTML='<div><img class=crop src="'+api('/crop/'+d.id+'.jpg')+'" onclick="openLightbox(this.src)" title="clica per ampliar"></div><div>'
    +'<div class=meta><span class="badge b-'+d.decision+'">'+d.decision+'</span> · tipus <span class="edcellc" data-edit=tip><span class=celltxt>'+esc(tjoin(etip)||'—')+'</span></span> · ⛪ <span class="edcellc" data-edit=ord><span class=celltxt>'+esc(tjoin(eord)||'—')+'</span></span> · <code>'+d.id+'</code>'+(d.flags&&d.flags.length?' · <span class=warn title="'+esc(flagTxt(d.flags))+'">⚠ '+esc(flagTxt(d.flags))+'</span>':'')+'</div>'
    +'<div class=act><label style="flex:0 0 auto;color:var(--soft);align-self:center">Lectura</label>'
    +'<input id=cgraf value="'+esc(d.graf||'')+'" style="flex:3;font-weight:600">'
    +'<button onclick="csave()">💾</button></div>'
    +(cands||'<div class=meta>(sense candidats)</div>')
    +'<div class=act><input id=csearch placeholder="🔍 cerca un nom al NGIB i mostra\\'l al mapa" style="flex:3"><button onclick="csearchMap()">al mapa</button></div>'
    +'<div class=act><input id=ccustom placeholder="…o escriu el nom NGIB correcte i Enter" style="flex:3"><button onclick="ccustom()">✓ Escrit</button></div>'
    +'<div class=act><button class=ok onclick="cok()"><kbd>C</kbd> ✓ Correcte</button><button class=none onclick="cnone()"><kbd>0</kbd> Cap</button>'
    +'<button class=trash onclick="ctrash()"><kbd>D</kbd> 🗑</button><button class=skip onclick="cskip()"><kbd>S</kbd> Saltar</button>'
    +'<button class=undo onclick="cundo()">↶ <kbd>U</kbd></button></div></div>';
  app.querySelectorAll('.cand').forEach(function(b){b.onclick=function(){cpick(b.dataset.g,b);};});
  app.querySelectorAll('.edcellc').forEach(function(sp){ sp.onclick=function(){
    if(sp.querySelector('.chkpop'))return; var which=sp.dataset.edit;
    openChecklist(sp, which==='tip'?TIPS:ORDRES, which==='tip'?etip:eord,
      function(vals){ if(which==='tip') ctipM(d.id,vals); else cordM(d.id,vals); },
      function(){ crender(); });
  };});
  cmap(d);
}
async function ctipM(id,vals){ vals=vals||[]; var d=dById(id); if(!await post({id:id,action:'tipus',tipus:vals})){crender();return;} if(d){ d.tipus=vals.length?vals.slice():d.tipus0.slice(); d.tipusEdited=d.tipus.join('|')!==d.tipus0.join('|'); } toast(vals.length?'🏷 '+vals.join(' · '):'🏷 (cap tipus)'); crender(); }
async function cordM(id,vals){ vals=vals||[]; var d=dById(id); if(!await post({id:id,action:'ordre',ordre:vals})){crender();return;} if(d){ d.ordre=vals.length?vals.slice():d.ordre0.slice(); d.ordreEdited=d.ordre.join('|')!==d.ordre0.join('|'); } toast(vals.length?'⛪ '+vals.join(' · '):'⛪ (cap orde)'); crender(); }
function toast(msg,cls){var t=$('#toast');t.className='';if(cls)t.classList.add(cls);t.textContent=msg;void t.offsetWidth;t.classList.add('show');clearTimeout(toast._t);toast._t=setTimeout(function(){t.classList.remove('show');},1300);}
function hit(sel){var b=document.querySelector('#app '+sel);if(b)b.classList.add('hit');}
function cgrafv(){var el=$('#cgraf'),d=queue[ci];if(!el||!d)return null;var v=el.value.trim();return (v&&v!==(d.graf||''))?v:null;}
function csetgraf(d,gv){if(gv){d.graf=gv;d.grafEdited=(gv!==d.graf0);}}  // aplica una edició de lectura al registre
function cadvance(){queue.splice(ci,1);if(ci>=queue.length)ci=queue.length-1;crender();}
async function cpick(g,el){var d=queue[ci];if(!el){try{el=document.querySelector('#app .cand[data-g="'+CSS.escape(g)+'"]');}catch(e){}}if(el)el.classList.add('sel');var gv=cgrafv();if(!await post({id:d.id,action:'pick',grafia:g,graf:gv})){if(el)el.classList.remove('sel');return;}csetgraf(d,gv);d.pend='pick';d.pendPick=g;d.review=(g===d.ngib?'revisat':'corregit');chist.push(d.id);toast('✓ '+g);setTimeout(cadvance,170);}
async function cnone(){var d=queue[ci];hit('.none');var gv=cgrafv();if(!await post({id:d.id,action:'none',graf:gv}))return;csetgraf(d,gv);d.pend='none';d.pendPick=null;d.review=null;chist.push(d.id);toast('Cap match','warn');setTimeout(cadvance,170);}
async function ctrash(){var d=queue[ci];hit('.trash');var gv=cgrafv();if(!await post({id:d.id,action:'trash',graf:gv}))return;csetgraf(d,gv);d.pend='trash';d.discarded=true;chist.push(d.id);toast('🗑 Brossa','bad');setTimeout(cadvance,170);}
async function cok(){var d=queue[ci];hit('.ok');var gv=cgrafv();if(!await post({id:d.id,action:'ok',graf:gv}))return;csetgraf(d,gv);d.pend='ok';chist.push(d.id);toast('✓ Correcte');setTimeout(cadvance,170);}
async function csave(){var d=queue[ci],g=cgrafv();if(!g){toast('(lectura igual)','warn');return;}if(!await post({id:d.id,action:'graf',graf:g}))return;csetgraf(d,g);toast('💾 Lectura desada');}
function cskip(){toast('Saltat');ci=(ci+1)%queue.length;crender();}
function ccustom(){var v=$('#ccustom').value.trim();if(v)cpick(v);}
function csearchMap(){
  if(!map)return; if(!searchLayer)searchLayer=L.layerGroup().addTo(map); searchLayer.clearLayers();
  var q=($('#csearch').value||'').trim().toLowerCase(); if(!q||!NGIB.length){toast('(escriu un nom)','warn');return;}
  var pts=[],d=queue[ci],n=0;
  for(var k=0;k<NGIB.length;k++){var a=NGIB[k]; if(a[0].toLowerCase().indexOf(q)<0)continue;
    var mk=L.circleMarker([a[3],a[2]],{radius:7,color:'#c0530a',weight:2,fillColor:'#e67e22',fillOpacity:.95});
    mk.bindTooltip('<b>'+esc(a[0])+'</b> · '+esc(a[1]||''),{direction:'top'});
    mk.on('click',(function(g){return function(){cpick(g);};})(a[0])); mk.addTo(searchLayer); pts.push([a[3],a[2]]); if(++n>80)break;}
  if(d&&d.lat!=null)pts.push([d.lat,d.lon]);
  if(pts.length)map.fitBounds(pts,{padding:[40,40]}); else toast('(cap resultat)','warn');
}
async function cundo(){var id=chist.pop();if(!id){toast('(res a desfer)','warn');return;}if(!await post({id:id,action:'undo'})){chist.push(id);return;}var d=dById(id);if(d){d.pend=null;d.pendPick=null;d.discarded=false;}toast('↶ Desfet');TARGET=id;cbuild();}
function initMap(){if(map)return;map=L.map('map');L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);ngibLayer=L.layerGroup().addTo(map);mlayer=L.layerGroup().addTo(map);map.setView([39.6,3.0],9);map.on('moveend',rngib);}
function rngib(){if(!ngibLayer||!NGIB.length||map.getZoom()<12)return;ngibLayer.clearLayers();var b=map.getBounds(),n=0;for(var k=0;k<NGIB.length;k++){var a=NGIB[k];if(a[3]<b.getSouth()||a[3]>b.getNorth()||a[2]<b.getWest()||a[2]>b.getEast())continue;var mk=L.circleMarker([a[3],a[2]],{radius:4,color:'#3a7d12',weight:1,fillColor:'#7cdb27',fillOpacity:.9});mk.bindTooltip('<b>'+esc(a[0])+'</b> · '+esc(a[1]||''));mk.on('click',(function(g){return function(){cpick(g);};})(a[0]));mk.addTo(ngibLayer);if(++n>700)break;}}
function clearMap(){if(mlayer)mlayer.clearLayers();if(searchLayer)searchLayer.clearLayers();}
function cmap(d){if(!map)return;map.invalidateSize();mlayer.clearLayers();if(searchLayer)searchLayer.clearLayers();var pts=[];if(d.lat!=null){L.circleMarker([d.lat,d.lon],{radius:8,color:'#c00',weight:2,fillColor:'#c00',fillOpacity:.45}).addTo(mlayer);pts.push([d.lat,d.lon]);}(d.candidates||[]).forEach(function(c,n){if(c.lat!=null){var mk=L.circleMarker([c.lat,c.lon],{radius:7,color:'#1d6b4f',weight:2,fillColor:'#37a37e',fillOpacity:.9});mk.bindTooltip('<b>'+(n+1)+'. '+esc(c.grafia)+'</b>');mk.on('click',(function(g){return function(){cpick(g);};})(c.grafia));mk.addTo(mlayer);pts.push([c.lat,c.lon]);}});if(pts.length)map.fitBounds(pts,{padding:[35,35],maxZoom:15});}
addEventListener('keydown',function(e){
  if(MODE!=='card'||!queue.length)return; if(e.ctrlKey||e.metaKey||e.altKey)return; if(e.target.tagName==='SELECT')return; if(e.target.tagName==='INPUT'){if(e.key==='Enter'){if(e.target.id==='ccustom')ccustom();else if(e.target.id==='csearch')csearchMap();else if(e.target.id==='cgraf')csave();}return;}
  var d=queue[ci],k=(e.key||'').toLowerCase();
  if(e.key>='1'&&e.key<='6'){var c=d.candidates[+e.key-1];if(c)cpick(c.grafia);}
  else if(e.key==='0')cnone();else if(k==='c')cok();else if(k==='d')ctrash();
  else if(k==='s'||e.key===' '){e.preventDefault();cskip();}
  else if(k==='u'){e.preventDefault();cundo();}
});
boot();
</script>`;

const send = (res, code, type, body) => { res.writeHead(code, { 'content-type': type, 'cache-control': 'no-store' }); res.end(body); };
const server = http.createServer((req, res) => {
  try {
  const u = new URL(req.url, 'http://x');
  if (req.method === 'GET' && u.pathname === '/') return send(res, 200, 'text/html; charset=utf8', PAGE);
  if (req.method === 'GET' && u.pathname === '/ngib') return send(res, 200, 'application/json', NGIB_JSON);
  if (req.method === 'GET' && u.pathname === '/table') {
    return send(res, 200, 'application/json', JSON.stringify({ rows: buildItems() }));
  }
  if (req.method === 'GET' && u.pathname === '/data') {
    // Same canonical records as the table; the card just renders them differently
    // (crop + candidates). Only items that have a rendered crop are kept.
    const items = buildItems().filter((it) => fs.existsSync(`${F.crops}/${it.id}.jpg`));
    return send(res, 200, 'application/json', JSON.stringify({ items }));
  }
  if (req.method === 'GET' && u.pathname.startsWith('/crop/')) {
    const p = `${F.crops}/${path.basename(u.pathname)}`;
    if (!fs.existsSync(p)) { res.writeHead(404); return res.end(); }
    return send(res, 200, 'image/jpeg', fs.readFileSync(p));
  }
  if (req.method === 'POST' && u.pathname === '/pick') {
    let body = ''; req.on('data', (c) => body += c);
    req.on('end', () => {
      try {
        const { id, action, grafia, graf, tipus, ordre } = JSON.parse(body || '{}');
        if (!id) return send(res, 400, 'application/json', '{"ok":false}');
        const cur = readJSON(F.curation, {});                      // THROWS if the file is corrupt
        const rec = cur[id] || (cur[id] = {});
        if (graf) rec.graf = graf;                                 // reading edits ride along any action
        if (action === 'graf') { if (!graf) delete rec.graf; }     // explicit empty graf -> clear the reading edit (for undo)
        else if (action === 'ordre') { const a = Array.isArray(ordre) ? ordre : (ordre ? [ordre] : []); if (a.length) rec.ordre = a; else delete rec.ordre; }  // axis 2, multi-value
        else if (action === 'tipus') { const a = Array.isArray(tipus) ? tipus : (tipus ? [tipus] : []); if (a.length) rec.tipus = a; else delete rec.tipus; }  // multi-value
        else if (action === 'pick' && grafia) { rec.ngib = grafia; rec.verdict = 'pick'; }
        else if (action === 'none') { rec.verdict = 'none'; delete rec.ngib; }  // "cap match" also clears any pick
        else if (action === 'ok') rec.verdict = 'ok';
        else if (action === 'trash') rec.verdict = 'trash';
        else if (action === 'undo') { delete rec.verdict; delete rec.ngib; }  // keep graf/tipus edits
        if (!Object.keys(rec).length) delete cur[id];             // drop empty records
        writeJSON(F.curation, cur);                                // atomic + .bak; never reached on a corrupt read
        send(res, 200, 'application/json', '{"ok":true}');
      } catch (e) {
        console.error('POST /pick failed:', e.message);
        if (!res.headersSent) send(res, 500, 'application/json', '{"ok":false,"error":"save"}');
      }
    });
    return;
  }
  res.writeHead(404); res.end();
  } catch (e) {
    console.error(e);
    if (!res.headersSent) { res.writeHead(500); res.end('{"ok":false,"error":"server"}'); }
  }
});
server.listen(4400, '127.0.0.1', () => console.log('Curació Mut 1683 → http://localhost:4400/'));
