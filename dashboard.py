"""
Pickaboo Price Dashboard  –  Flask single-file app
Run: python dashboard.py  →  http://localhost:5000
"""
import sqlite3, os
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)
DB_FILE = 'pickaboo_prices.db'

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def q(sql, params=()):
    conn = db()
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows

def q1(sql, params=()):
    conn = db()
    r = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(r) if r else {}

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pickaboo Price Tracker · CamelBoo</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#080810;--surface:#0e0e1c;--surface2:#13132a;
  --purple:#7c3aed;--purple-light:#a855f7;--cyan:#06b6d4;--gold:#f59e0b;
  --green:#10b981;--red:#ef4444;
  --glass:rgba(255,255,255,0.04);--glass2:rgba(255,255,255,0.07);
  --border:rgba(255,255,255,0.08);--border2:rgba(255,255,255,0.14);
  --text:#e2e8f0;--muted:#64748b;--muted2:#94a3b8;
  --sidebar:280px;
}
html{height:100%}
body{
  font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);
  min-height:100vh;display:flex;flex-direction:column;
  background-image:
    radial-gradient(ellipse 60% 40% at 10% 20%,rgba(124,58,237,.12) 0,transparent 60%),
    radial-gradient(ellipse 50% 50% at 90% 80%,rgba(6,182,212,.08) 0,transparent 60%);
}
a{color:inherit;text-decoration:none}
button{font-family:'Inter',sans-serif}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:99px}

/* HEADER */
.header{
  position:sticky;top:0;z-index:200;
  display:flex;align-items:center;gap:1.25rem;
  padding:.75rem 1.25rem;
  background:rgba(8,8,16,.88);
  backdrop-filter:blur(20px);
  border-bottom:1px solid var(--border);
}
.logo{
  font-weight:800;font-size:1.2rem;white-space:nowrap;
  background:linear-gradient(130deg,var(--purple-light),var(--cyan));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
}
.logo span{font-weight:300;opacity:.7;font-size:.9rem}
.header-stats{display:flex;gap:1.25rem;margin-left:.25rem}
.hstat{display:flex;flex-direction:column}
.hstat-label{font-size:.6rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.hstat-val{font-size:.9rem;font-weight:700;color:var(--gold)}
.spacer{flex:1}
.controls-wrap{display:flex;align-items:center;gap:.6rem}

.search-wrap{position:relative;width:220px}
.search-wrap input{
  width:100%;padding:.45rem .8rem .45rem 2.2rem;
  background:var(--glass2);border:1px solid var(--border2);
  border-radius:8px;color:var(--text);font-size:.85rem;outline:none;
  transition:border-color .2s;
}
.search-wrap input:focus{border-color:var(--purple)}
.search-wrap .ico{
  position:absolute;left:.65rem;top:50%;transform:translateY(-50%);
  color:var(--muted);font-size:.85rem;pointer-events:none;
}
.sort-sel{
  padding:.45rem .75rem;background:var(--glass2);
  border:1px solid var(--border2);border-radius:8px;
  color:var(--text);font-size:.85rem;outline:none;cursor:pointer;
}

/* ALL-TIME LOW FILTER BTN */
.atl-btn{
  display:flex;align-items:center;gap:.4rem;
  padding:.45rem .85rem;background:var(--glass2);
  border:1px solid var(--border2);border-radius:8px;
  color:var(--muted2);font-size:.82rem;font-weight:600;
  cursor:pointer;transition:all .2s;user-select:none;
}
.atl-btn:hover{color:var(--text);border-color:var(--green)}
.atl-btn.active{
  background:rgba(16,185,129,.18);border-color:var(--green);
  color:var(--green);box-shadow:0 0 12px rgba(16,185,129,.3);
}

/* LAYOUT */
.layout{display:flex;flex:1;overflow:hidden;height:calc(100vh - 53px)}

/* SIDEBAR */
.sidebar{
  width:var(--sidebar);flex-shrink:0;
  background:var(--surface);
  border-right:1px solid var(--border);
  overflow-y:auto;padding:.75rem 0;
  display:flex;flex-direction:column;
}
.sidebar-hdr{
  display:flex;align-items:center;justify-content:space-between;
  padding:.4rem 1rem .6rem;border-bottom:1px solid var(--border);
  margin-bottom:.5rem;
}
.sidebar-title{
  font-size:.68rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.1em;color:var(--muted);
}
.toggle-all-btn{
  background:none;border:none;color:var(--cyan);font-size:.72rem;
  cursor:pointer;font-weight:600;padding:.2rem .4rem;border-radius:4px;
}
.toggle-all-btn:hover{background:rgba(6,182,212,.1)}

.cat-group{margin-bottom:.15rem}
.cat-parent{
  display:flex;align-items:center;gap:.5rem;
  padding:.45rem 1rem;cursor:pointer;
  font-size:.83rem;font-weight:500;color:var(--muted2);
  transition:all .15s;border-left:3px solid transparent;
  user-select:none;
}
.cat-parent:hover{color:var(--text);background:var(--glass)}
.cat-parent.active{color:var(--cyan);border-left-color:var(--cyan);background:rgba(6,182,212,.08)}
.cat-parent .arrow{
  margin-left:auto;font-size:.65rem;
  transition:transform .2s;color:var(--muted);
}
.cat-parent.open .arrow{transform:rotate(90deg)}
.cat-num{
  font-size:.7rem;padding:.15rem .45rem;border-radius:99px;
  background:rgba(255,255,255,.06);color:var(--muted);font-weight:600;
  margin-left:auto;
}
.cat-parent.active .cat-num{background:rgba(6,182,212,.2);color:var(--cyan)}

.cat-children{display:none;padding:0 0 .2rem 1.25rem}
.cat-group.expanded .cat-children{display:block}
.cat-child{
  display:flex;align-items:center;justify-content:space-between;
  padding:.32rem .8rem;cursor:pointer;font-size:.78rem;color:var(--muted);
  border-radius:6px;transition:all .15s;margin:.1rem 0;
}
.cat-child:hover{color:var(--text);background:var(--glass)}
.cat-child.active{color:var(--purple-light);background:rgba(124,58,237,.12)}
.cat-child.active .cat-num{background:rgba(124,58,237,.25);color:var(--purple-light)}

/* CONTENT */
.content{flex:1;overflow-y:auto;padding:1.25rem}
.section-hdr{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:1rem;
}
.section-title-wrap{display:flex;align-items:center;gap:.6rem}
.section-hdr h2{font-size:.95rem;font-weight:600;color:var(--muted2)}
.count-chip{
  font-size:.72rem;padding:.18rem .55rem;border-radius:99px;
  background:rgba(124,58,237,.15);color:var(--purple-light);font-weight:600;
}

/* COMPACT PRODUCT GRID */
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(165px,1fr));
  gap:.75rem;
}
.card{
  background:var(--glass);border:1px solid var(--border);border-radius:12px;
  cursor:pointer;transition:all .2s cubic-bezier(.4,0,.2,1);
  display:flex;flex-direction:column;overflow:hidden;
  position:relative;
}
.card::before{
  content:'';position:absolute;inset:0;border-radius:12px;
  background:linear-gradient(135deg,rgba(124,58,237,.1),rgba(6,182,212,.05));
  opacity:0;transition:opacity .2s;pointer-events:none;
}
.card:hover{
  transform:translateY(-4px);
  box-shadow:0 14px 28px -10px rgba(124,58,237,.35);
  border-color:rgba(124,58,237,.4);
}
.card:hover::before{opacity:1}
.card-img-wrap{
  padding:.6rem;background:rgba(255,255,255,.97);
  border-radius:10px 10px 0 0;height:115px;
  display:flex;align-items:center;justify-content:center;
}
.card-img{max-width:100%;max-height:100px;object-fit:contain}
.card-body{padding:.65rem;flex:1;display:flex;flex-direction:column;gap:.35rem}
.card-name{
  font-size:.76rem;font-weight:500;line-height:1.3;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
}
.card-foot{display:flex;align-items:center;justify-content:space-between;margin-top:auto;padding-top:.2rem}
.price{
  font-size:.92rem;font-weight:700;
  background:linear-gradient(120deg,var(--purple-light),var(--cyan));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.original-price{font-size:.68rem;color:var(--muted);text-decoration:line-through}
.badge{
  position:absolute;top:6px;right:6px;z-index:1;
  padding:.15rem .45rem;border-radius:99px;font-size:.65rem;font-weight:700;
}
.badge-disc{background:#ef4444;color:#fff;box-shadow:0 3px 8px rgba(239,68,68,.4)}
.badge-atl{background:var(--green);color:#fff;box-shadow:0 3px 8px rgba(16,185,129,.4);left:6px;right:auto}
.badge-out{background:rgba(100,116,139,.3);color:var(--muted2)}
.stock-dot{
  width:6px;height:6px;border-radius:50%;display:inline-block;margin-right:.3rem;
}
.stock-dot.in{background:var(--green);box-shadow:0 0 6px rgba(16,185,129,.5)}
.stock-dot.out{background:var(--muted)}
.unit-tip{font-size:.66rem;color:var(--cyan);font-weight:500}

/* FIT SCREEN MODAL */
.overlay{
  position:fixed;inset:0;z-index:500;
  background:rgba(0,0,0,.8);backdrop-filter:blur(12px);
  display:flex;align-items:center;justify-content:center;
  opacity:0;pointer-events:none;transition:opacity .25s;
}
.overlay.show{opacity:1;pointer-events:auto}
.modal{
  background:var(--surface);border:1px solid var(--border2);
  border-radius:18px;width:min(95vw,1100px);height:min(90vh,750px);
  display:flex;flex-direction:column;
  transform:scale(.96) translateY(20px);
  transition:transform .25s cubic-bezier(.4,0,.2,1);
  box-shadow:0 35px 70px -15px rgba(0,0,0,.85),
             0 0 0 1px rgba(124,58,237,.2);
  overflow:hidden;
}
.overlay.show .modal{transform:scale(1) translateY(0)}
.modal-hdr{
  padding:1rem 1.25rem;border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:.9rem;flex-shrink:0;
}
.modal-thumb{
  width:60px;height:60px;object-fit:contain;
  background:#fff;border-radius:8px;padding:4px;flex-shrink:0;
}
.modal-meta{flex:1;min-width:0}
.modal-title{font-size:.98rem;font-weight:600;line-height:1.3;margin-bottom:.2rem}
.modal-sub{font-size:.76rem;color:var(--muted2)}
.close-btn{
  background:var(--glass2);border:1px solid var(--border);
  color:var(--muted2);border-radius:8px;width:32px;height:32px;
  cursor:pointer;font-size:1rem;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  transition:all .15s;
}
.close-btn:hover{background:var(--glass);color:var(--text)}

.modal-body{
  flex:1;min-height:0;padding:1.25rem;
  display:flex;flex-direction:column;gap:1rem;
  overflow:hidden;
}

.pstats{
  display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;flex-shrink:0;
}
.pstat{
  background:var(--surface2);border:1px solid var(--border);border-radius:10px;
  padding:.75rem .9rem;display:flex;flex-direction:column;gap:.2rem;
}
.pstat-label{font-size:.6rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.pstat-val{font-size:1.1rem;font-weight:700}
.pstat-val.curr{color:var(--text)}
.pstat-val.low {color:var(--green)}
.pstat-val.high{color:var(--red)}
.pstat-val.unit{color:var(--cyan)}

.alert-bar{
  display:none;flex-shrink:0;
  background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);
  border-radius:8px;padding:.6rem 1rem;color:var(--green);
  font-weight:500;font-size:.82rem;align-items:center;gap:.6rem;
}
.alert-bar.show{display:flex}

.chart-wrap{
  flex:1;min-height:0;width:100%;height:100%;
  position:relative;
}

/* EMPTY / LOADING */
.empty{
  grid-column:1/-1;text-align:center;padding:4rem 2rem;
  color:var(--muted);display:flex;flex-direction:column;align-items:center;gap:1rem;
}
.empty-icon{font-size:2.5rem;opacity:.4}
.empty-msg{font-size:.95rem;font-weight:500}
.empty-sub{font-size:.8rem}

/* PAGINATION */
.pager{display:flex;justify-content:center;gap:.4rem;padding:1rem 0 0}
.pager-btn{
  padding:.35rem .75rem;background:var(--glass2);border:1px solid var(--border);
  border-radius:6px;color:var(--muted2);cursor:pointer;font-size:.8rem;
  transition:all .15s;
}
.pager-btn:hover,.pager-btn.active{background:var(--purple);color:#fff;border-color:var(--purple)}
.pager-btn:disabled{opacity:.35;cursor:not-allowed}
</style>
</head>
<body>

<!-- HEADER -->
<header class="header">
  <div class="logo">Pickaboo <span>Tracker</span></div>
  <div class="header-stats">
    <div class="hstat"><span class="hstat-label">Products</span><span class="hstat-val" id="hProducts">—</span></div>
    <div class="hstat"><span class="hstat-label">Categories</span><span class="hstat-val" id="hCats">—</span></div>
    <div class="hstat"><span class="hstat-label">Last Scrape</span><span class="hstat-val" id="hDate">—</span></div>
  </div>
  <div class="spacer"></div>
  <div class="controls-wrap">
    <button class="atl-btn" id="atlBtn" onclick="toggleAtlFilter()">
      <span>📉</span> All-Time Low
    </button>
    <div class="search-wrap">
      <span class="ico">🔍</span>
      <input type="text" id="searchBox" placeholder="Search products…" oninput="debounce()">
    </div>
    <select class="sort-sel" id="sortSel" onchange="loadProducts(1)">
      <option value="newest">Newest</option>
      <option value="price_asc">Price ↑</option>
      <option value="price_desc">Price ↓</option>
      <option value="discount">Discount %</option>
    </select>
  </div>
</header>

<!-- LAYOUT -->
<div class="layout">
  <!-- SIDEBAR -->
  <aside class="sidebar">
    <div class="sidebar-hdr">
      <span class="sidebar-title">Categories</span>
      <button class="toggle-all-btn" onclick="toggleExpandAll()">Expand All</button>
    </div>
    <div class="cat-group">
      <div class="cat-parent active" id="cat-all" onclick="selectCat('','','',this)">
        <span>🏠 All Products</span>
        <span class="cat-num" id="cat-all-num">0</span>
      </div>
    </div>
    <div id="catTree"></div>
  </aside>

  <!-- CONTENT -->
  <main class="content">
    <div class="section-hdr">
      <div class="section-title-wrap">
        <h2 id="sectionTitle">All Products</h2>
        <span class="count-chip" id="countChip">0 items</span>
      </div>
    </div>
    <div class="grid" id="grid"></div>
    <div class="pager" id="pager"></div>
  </main>
</div>

<!-- MODAL -->
<div class="overlay" id="overlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-hdr">
      <img id="mThumb" class="modal-thumb" src="" alt="">
      <div class="modal-meta">
        <div class="modal-title" id="mTitle"></div>
        <div class="modal-sub" id="mSub"></div>
      </div>
      <button class="close-btn" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body">
      <div class="pstats">
        <div class="pstat"><div class="pstat-label">Current Price</div><div class="pstat-val curr" id="mCurr">৳—</div></div>
        <div class="pstat"><div class="pstat-label">Lowest Ever 🟢</div><div class="pstat-val low"  id="mLow">৳—</div></div>
        <div class="pstat"><div class="pstat-label">Highest Ever 🔴</div><div class="pstat-val high" id="mHigh">৳—</div></div>
        <div class="pstat"><div class="pstat-label">Unit Price 📐</div><div class="pstat-val unit"  id="mUnit">—</div></div>
      </div>
      <div class="alert-bar" id="alertBar">
        <span>🔥</span>
        <span id="alertMsg"></span>
      </div>
      <div class="chart-wrap"><canvas id="priceChart"></canvas></div>
    </div>
  </div>
</div>

<script>
// STATE
let curCat='', curPage=1, totalPages=1, searchTimer=null, chart=null, filterAtl=false, allExpanded=false;

// INIT
async function init(){
  await Promise.all([loadStats(), loadCats()]);
  loadProducts(1);
}

// STATS
async function loadStats(){
  const d = await api('/api/stats');
  document.getElementById('hProducts').textContent = (d.total_products||0).toLocaleString();
  document.getElementById('hCats').textContent     = (d.total_cats||0).toLocaleString();
  document.getElementById('cat-all-num').textContent = (d.total_products||0).toLocaleString();
  document.getElementById('hDate').textContent     = d.last_scraped
    ? new Date(d.last_scraped).toLocaleDateString('en-BD',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})
    : 'Never';
}

// CATEGORIES & NUMBERS
async function loadCats(){
  const cats = await api('/api/categories');
  const tree = document.getElementById('catTree');
  const parents = cats.filter(c=>!c.parent_id);
  const childMap = {};
  cats.filter(c=>c.parent_id).forEach(c=>{
    (childMap[c.parent_id]=childMap[c.parent_id]||[]).push(c);
  });

  parents.forEach(p=>{
    const group = document.createElement('div');
    group.className='cat-group';
    const children = childMap[p.id]||[];
    const hasChildren = children.length>0;
    
    // Sum counts for parent
    const childSum = children.reduce((sum, c)=> sum + (c.prod_count||0), 0);
    const totalCatCount = (p.prod_count||0) + childSum;

    group.innerHTML=`
      <div class="cat-parent" id="cp-${p.id}"
           onclick="handleParentClick('${p.id}','${esc(p.name)}',this,event)">
        <span>${p.name}</span>
        ${hasChildren?'<span class="arrow">›</span>':''}
        <span class="cat-num">${totalCatCount}</span>
      </div>
      ${hasChildren?`<div class="cat-children">
        ${children.map(c=>`
          <div class="cat-child" id="cc-${c.id}"
               onclick="selectCat('${c.id}','${esc(c.name)}','child',this)">
            <span>${c.name}</span>
            <span class="cat-num">${c.prod_count||0}</span>
          </div>`).join('')}
      </div>`:''}`;
    tree.appendChild(group);
  });
}

function esc(s){return (s||'').replace(/'/g,"\\'").replace(/"/g,'\\"')}

function handleParentClick(id,name,el,ev){
  const group=el.closest('.cat-group');
  const hasChildren=!!group.querySelector('.cat-children');
  if(hasChildren){
    group.classList.toggle('expanded');
    el.classList.toggle('open');
  }
  selectCat(id,name,'parent',el);
}

function toggleExpandAll(){
  allExpanded = !allExpanded;
  document.querySelectorAll('.cat-group').forEach(g=>{
    if(allExpanded) g.classList.add('expanded');
    else g.classList.remove('expanded');
  });
  document.querySelectorAll('.cat-parent').forEach(p=>{
    if(allExpanded) p.classList.add('open');
    else p.classList.remove('open');
  });
  document.querySelector('.toggle-all-btn').textContent = allExpanded ? 'Collapse All' : 'Expand All';
}

function toggleAtlFilter(){
  filterAtl = !filterAtl;
  document.getElementById('atlBtn').classList.toggle('active', filterAtl);
  loadProducts(1);
}

function selectCat(id,name,type,el){
  curCat=id;
  document.querySelectorAll('.cat-parent,.cat-child,.cat-parent[id=cat-all]')
    .forEach(x=>x.classList.remove('active'));
  if(el) el.classList.add('active');
  document.getElementById('sectionTitle').textContent=name||'All Products';
  loadProducts(1);
}

// COMPACT PRODUCT GRID
async function loadProducts(page=1){
  curPage=page;
  const grid=document.getElementById('grid');
  grid.innerHTML='<div class="empty"><div class="empty-icon">⏳</div><div class="empty-msg">Loading…</div></div>';

  const search=document.getElementById('searchBox').value;
  const sort=document.getElementById('sortSel').value;
  const params=new URLSearchParams({
    category_id:curCat,
    search,
    sort,
    page,
    atl: filterAtl ? 1 : 0
  });
  const data=await api('/api/products?'+params);

  document.getElementById('countChip').textContent=`${(data.total||0).toLocaleString()} items`;
  totalPages=Math.ceil((data.total||0)/40);
  renderPager();

  grid.innerHTML='';
  if(!data.products||data.products.length===0){
    grid.innerHTML=`<div class="empty">
      <div class="empty-icon">📭</div>
      <div class="empty-msg">${filterAtl ? 'No All-Time Low items found' : 'No products found'}</div>
      <div class="empty-sub">Try adjusting your filters or running a fresh scrape.</div>
    </div>`;
    return;
  }

  data.products.forEach(p=>{
    const price=p.special_price>0?p.special_price:p.price;
    const inStock=p.stock_available===1;
    const isAtl=p.is_atl===1;
    const card=document.createElement('div');
    card.className='card';
    card.onclick=()=>openModal(p);
    card.innerHTML=`
      ${isAtl?`<div class="badge badge-atl">🔥 Lowest</div>`:''}
      ${p.discount>0?`<div class="badge badge-disc">−${Math.round(p.discount)}%</div>`:''}
      ${!inStock?`<div class="badge badge-out">Out of stock</div>`:''}
      <div class="card-img-wrap">
        <img class="card-img" src="${p.product_img||''}" alt="${p.name}"
             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><text y=%2250%25%22 x=%2250%25%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 font-size=%2224%22>📦</text></svg>'">
      </div>
      <div class="card-body">
        <div class="card-name" title="${p.name}">${p.name}</div>
        ${p.unit&&p.unit_value?`<div class="unit-tip">৳${(price/p.unit_value).toFixed(1)} / ${p.unit}</div>`:''}
        <div class="card-foot">
          <div>
            <span class="stock-dot ${inStock?'in':'out'}"></span>
            ${p.discount>0?`<span class="original-price">৳${(p.price||0).toLocaleString()}</span>`:''}
          </div>
          <span class="price">৳${(price||0).toLocaleString()}</span>
        </div>
      </div>`;
    grid.appendChild(card);
  });
}

function renderPager(){
  const pg=document.getElementById('pager');
  pg.innerHTML='';
  if(totalPages<=1) return;
  const mkBtn=(lbl,page,disabled,active)=>{
    const b=document.createElement('button');
    b.className='pager-btn'+(active?' active':'');
    b.textContent=lbl; b.disabled=disabled;
    b.onclick=()=>{ loadProducts(page); window.scrollTo(0,0); };
    return b;
  };
  pg.appendChild(mkBtn('‹ Prev',curPage-1,curPage===1));
  const start=Math.max(1,curPage-2), end=Math.min(totalPages,curPage+2);
  for(let i=start;i<=end;i++) pg.appendChild(mkBtn(i,i,false,i===curPage));
  pg.appendChild(mkBtn('Next ›',curPage+1,curPage===totalPages));
}

// FIT SCREEN MODAL
async function openModal(p){
  const overlay=document.getElementById('overlay');
  document.getElementById('mThumb').src=p.product_img||'';
  document.getElementById('mTitle').textContent=p.name;
  document.getElementById('mSub').textContent=`SKU: ${p.sku||'—'}  ·  Category: ${p.category_name||'—'}`;
  overlay.classList.add('show');

  const data=await api(`/api/product/${p.id}/history`);
  const h=data.history||[];
  if(h.length===0){
    ['mCurr','mLow','mHigh','mUnit'].forEach(id=>document.getElementById(id).textContent='—');
    return;
  }

  const prices=h.map(r=>r.special_price>0?r.special_price:r.price);
  const curr=prices[prices.length-1];
  const low=Math.min(...prices), high=Math.max(...prices);
  const avg=prices.reduce((a,b)=>a+b,0)/prices.length;

  document.getElementById('mCurr').textContent=`৳${curr.toLocaleString()}`;
  document.getElementById('mLow').textContent =`৳${low.toLocaleString()}`;
  document.getElementById('mHigh').textContent=`৳${high.toLocaleString()}`;

  if(p.unit&&p.unit_value){
    document.getElementById('mUnit').textContent=`৳${(curr/p.unit_value).toFixed(2)} / ${p.unit}`;
  } else {
    document.getElementById('mUnit').textContent='N/A';
  }

  const alertBar=document.getElementById('alertBar');
  if(curr<=low){
    document.getElementById('alertMsg').textContent=
      `🔥 ALL-TIME LOW PRICE! This product is currently at its lowest recorded price (৳${curr.toLocaleString()}).`;
    alertBar.classList.add('show');
  } else if(curr<avg*0.95){
    const pct=((avg-curr)/avg*100).toFixed(1);
    document.getElementById('alertMsg').textContent=
      `Price is ${pct}% below average (avg ৳${Math.round(avg).toLocaleString()}) — Great deal!`;
    alertBar.classList.add('show');
  } else {
    alertBar.classList.remove('show');
  }

  renderChart(h, p.unit, p.unit_value);
}

function closeModal(){
  document.getElementById('overlay').classList.remove('show');
}

function renderChart(h, unit, unitVal){
  if(chart){ chart.destroy(); chart=null; }
  const ctx=document.getElementById('priceChart').getContext('2d');

  const grad=ctx.createLinearGradient(0,0,0,280);
  grad.addColorStop(0,'rgba(124,58,237,.55)');
  grad.addColorStop(1,'rgba(124,58,237,0)');

  const labels=h.map(r=>new Date(r.scraped_at).toLocaleDateString('en-BD',{month:'short',day:'numeric'}));
  const prices=h.map(r=>r.special_price>0?r.special_price:r.price);

  chart=new Chart(ctx,{
    type:'line',
    data:{
      labels,
      datasets:[{
        label:'Price ৳',data:prices,
        borderColor:'#7c3aed',backgroundColor:grad,
        borderWidth:2.5,pointBackgroundColor:'#06b6d4',
        pointBorderColor:'#fff',pointRadius:4,pointHoverRadius:6,
        fill:true,tension:.4
      }]
    },
    options:{
      responsive:true,maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{
        legend:{display:false},
        tooltip:{
          backgroundColor:'rgba(11,11,25,.95)',
          borderColor:'rgba(255,255,255,.1)',borderWidth:1,
          titleFont:{family:'Inter',size:12},
          bodyFont:{family:'Inter',size:13,weight:'bold'},
          padding:12,
          callbacks:{
            label(ctx){
              let s=`৳${ctx.parsed.y.toLocaleString()}`;
              if(unit&&unitVal) s+=`  (৳${(ctx.parsed.y/unitVal).toFixed(2)}/${unit})`;
              return s;
            }
          }
        }
      },
      scales:{
        y:{
          grid:{color:'rgba(255,255,255,.04)'},
          ticks:{color:'#94a3b8',font:{family:'Inter',size:11}},
          border:{display:false}
        },
        x:{
          grid:{display:false},
          ticks:{color:'#94a3b8',font:{family:'Inter',size:11},maxRotation:0},
          border:{display:false}
        }
      }
    }
  });
}

// UTILS
async function api(url){
  try{ const r=await fetch(url); return await r.json(); }
  catch(e){ console.error(url,e); return {}; }
}
function debounce(){ clearTimeout(searchTimer); searchTimer=setTimeout(()=>loadProducts(1),400); }
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeModal(); });

init();
</script>
</body>
</html>"""

# API ROUTES

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/stats')
def stats():
    total_products = q1("SELECT COUNT(*) AS c FROM products").get('c', 0)
    total_cats     = q1("SELECT COUNT(*) AS c FROM categories").get('c', 0)
    last_scraped   = q1("SELECT MAX(scraped_at) AS t FROM price_history").get('t')
    return jsonify(total_products=total_products, total_cats=total_cats, last_scraped=last_scraped)

@app.route('/api/categories')
def categories():
    rows = q("""
        SELECT c.id, c.name, c.slug, c.parent_id,
               COALESCE(p.cnt, 0) as prod_count
        FROM categories c
        LEFT JOIN (
            SELECT category_id, COUNT(*) as cnt
            FROM products
            GROUP BY category_id
        ) p ON c.id = p.category_id
        ORDER BY c.name
    """)
    return jsonify(rows)

@app.route('/api/products')
def products():
    cat_id  = request.args.get('category_id', '')
    search  = request.args.get('search', '')
    sort    = request.args.get('sort', 'newest')
    atl     = request.args.get('atl', '0') == '1'
    page    = max(1, int(request.args.get('page', 1)))
    per     = 40
    offset  = (page - 1) * per

    where, params = [], []
    if cat_id:
        where.append("(p.category_id = ? OR p.category_id IN (SELECT id FROM categories WHERE parent_id=?))")
        params += [cat_id, cat_id]
    if search:
        where.append("p.name LIKE ?")
        params.append(f"%{search}%")
    if atl:
        where.append("""
            COALESCE(NULLIF(h.special_price,0), h.price) <= (
                SELECT MIN(COALESCE(NULLIF(special_price,0), price))
                FROM price_history
                WHERE product_id = p.id
            )
        """)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    order = {
        'price_asc':  "ORDER BY COALESCE(NULLIF(h.special_price,0),h.price) ASC",
        'price_desc': "ORDER BY COALESCE(NULLIF(h.special_price,0),h.price) DESC",
        'discount':   "ORDER BY h.discount DESC",
    }.get(sort, "ORDER BY p.rowid DESC")

    base_sql = f"""
        FROM products p
        JOIN (
            SELECT product_id, price, special_price, discount, stock_available
            FROM price_history
            WHERE id IN (SELECT MAX(id) FROM price_history GROUP BY product_id)
        ) h ON p.id = h.product_id
        {where_sql}
    """

    # Check if current price is all time low
    atl_check = """
        (COALESCE(NULLIF(h.special_price,0), h.price) <= (
            SELECT MIN(COALESCE(NULLIF(special_price,0), price))
            FROM price_history
            WHERE product_id = p.id
        )) as is_atl
    """

    total  = q1(f"SELECT COUNT(*) AS c {base_sql}", params).get('c', 0)
    rows   = q(f"SELECT p.*, h.price, h.special_price, h.discount, h.stock_available, {atl_check} {base_sql} {order} LIMIT {per} OFFSET {offset}", params)
    return jsonify(products=rows, total=total, page=page)

@app.route('/api/product/<pid>/history')
def product_history(pid):
    rows = q("""
        SELECT price, special_price, discount, stock_available,
               scraped_at
        FROM price_history WHERE product_id=? ORDER BY scraped_at
    """, (pid,))
    return jsonify(history=rows)

if __name__ == '__main__':
    if not os.path.exists(DB_FILE):
        print("⚠ Database not found. Run: python scraper.py first.")
    app.run(debug=True, port=5000)
