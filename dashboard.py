"""
Pickaboo Price Dashboard  -  Flask single-file app
Run: python dashboard.py  ->  http://localhost:5000

Includes:
  - SteamDB-style price history graphs (range toggle, price/discount metric, low watermark)
  - Analytics board: KPIs, biggest drops, hottest discounts, category distribution
  - Watchlist (localStorage) + price alerts
  - Filters (all-time-low / on-sale / in-stock), extra sorts, grid/list views
"""
import sqlite3, os
from datetime import datetime
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)
DB_FILE = 'pickaboo_prices.db'

LATEST_H = """
    SELECT product_id, price, special_price, discount, stock_available,
           COALESCE(NULLIF(special_price,0), price) AS eff
    FROM price_history
    WHERE id IN (SELECT MAX(id) FROM price_history GROUP BY product_id)
"""
METRICS_H = """
    SELECT product_id,
           MIN(COALESCE(NULLIF(special_price,0), price)) AS hist_min,
           MAX(COALESCE(NULLIF(special_price,0), price)) AS hist_max,
           AVG(COALESCE(NULLIF(special_price,0), price)) AS hist_avg
    FROM price_history GROUP BY product_id
"""

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
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --ink:#06060b;--surface:#0b0b14;--surface2:#10101d;--surface3:#161627;
  --line:rgba(255,255,255,.07);--line2:rgba(255,255,255,.15);
  --text:#e8eaf2;--muted:#8a93a6;--faint:#5b6472;
  --violet:#8b5cf6;--violet-soft:rgba(139,92,246,.16);
  --cyan:#22d3ee;--cyan-soft:rgba(34,211,238,.13);
  --up:#34d399;--down:#fb7185;--gold:#fbbf24;
  --up-soft:rgba(52,211,153,.13);--down-soft:rgba(251,113,133,.13);
  --gold-soft:rgba(251,191,36,.15);
  --glass:rgba(255,255,255,.035);
  --radius:12px;--radius-lg:16px;
  --font-body:'Inter',system-ui,sans-serif;
  --font-display:'Space Grotesk',sans-serif;
  --font-mono:'JetBrains Mono',ui-monospace,SFMono-Regular,monospace;
  --sidebar:282px;
}
html{height:100%}
body{
  font-family:var(--font-body);background:var(--ink);color:var(--text);
  min-height:100vh;display:flex;flex-direction:column;
  background-image:
    radial-gradient(ellipse 60% 42% at 8% -6%,rgba(139,92,246,.13) 0,transparent 60%),
    radial-gradient(ellipse 46% 46% at 100% 100%,rgba(34,211,238,.07) 0,transparent 60%);
  background-attachment:fixed;
}
a{color:inherit;text-decoration:none}
button{font-family:var(--font-body)}
input,select{font-family:var(--font-body)}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--line2);border-radius:99px}
:focus-visible{outline:2px solid var(--cyan);outline-offset:2px;border-radius:4px}

/* HEADER */
.header{
  position:sticky;top:0;z-index:200;
  display:flex;align-items:center;gap:1.1rem;
  padding:.7rem 1.25rem;
  background:rgba(6,6,11,.86);backdrop-filter:blur(20px);
  border-bottom:1px solid var(--line);
}
.logo{
  font-family:var(--font-display);font-weight:700;font-size:1.22rem;white-space:nowrap;
  letter-spacing:.01em;
  background:linear-gradient(120deg,#c4b5fd 0%,#8b5cf6 45%,#22d3ee 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.logo .tick{font-family:var(--font-mono);font-weight:500;font-size:.72rem;letter-spacing:.12em;
  -webkit-text-fill-color:var(--faint);display:block;text-transform:uppercase}
.header-stats{display:flex;gap:1.15rem;margin-left:.2rem}
.hstat{display:flex;flex-direction:column}
.hstat-label{font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;color:var(--faint);font-weight:600}
.hstat-val{font-family:var(--font-mono);font-size:.9rem;font-weight:700;color:var(--gold);font-variant-numeric:tabular-nums}
.hstat-val .unit{color:var(--muted);font-size:.7rem;font-weight:500}
.spacer{flex:1}
.controls-wrap{display:flex;align-items:center;gap:.55rem;flex-wrap:wrap;justify-content:flex-end}

.tbtn{
  display:flex;align-items:center;gap:.4rem;
  padding:.45rem .8rem;background:var(--surface2);
  border:1px solid var(--line);border-radius:8px;
  color:var(--muted);font-size:.78rem;font-weight:600;
  cursor:pointer;transition:all .2s;user-select:none;white-space:nowrap;
}
.tbtn:hover{color:var(--text);border-color:var(--line2)}
.tbtn.active{background:var(--up-soft);border-color:var(--up);color:var(--up);box-shadow:0 0 14px rgba(52,211,153,.18)}
.tbtn.active.atl{background:var(--gold-soft);border-color:var(--gold);color:var(--gold);box-shadow:0 0 14px rgba(251,191,36,.2)}
.tbtn.active.sale{background:var(--down-soft);border-color:var(--down);color:var(--down);box-shadow:0 0 14px rgba(251,113,133,.18)}
.tbtn.active.stock{background:var(--cyan-soft);border-color:var(--cyan);color:var(--cyan);box-shadow:0 0 14px rgba(34,211,238,.18)}

.search-wrap{position:relative;width:210px}
.search-wrap input{
  width:100%;padding:.45rem .8rem .45rem 2.1rem;
  background:var(--surface2);border:1px solid var(--line);
  border-radius:8px;color:var(--text);font-size:.82rem;outline:none;
  transition:border-color .2s;
}
.search-wrap input:focus{border-color:var(--violet)}
.search-wrap .ico{position:absolute;left:.6rem;top:50%;transform:translateY(-50%);color:var(--faint);font-size:.85rem;pointer-events:none}
.sort-sel{
  padding:.45rem .7rem;background:var(--surface2);
  border:1px solid var(--line);border-radius:8px;
  color:var(--text);font-size:.8rem;outline:none;cursor:pointer;
}
.menu-btn{display:none;background:var(--surface2);border:1px solid var(--line);color:var(--text);border-radius:8px;width:34px;height:34px;cursor:pointer;font-size:.95rem}

/* LAYOUT */
.layout{display:flex;flex:1;overflow:hidden;height:calc(100vh - 57px)}
.sidebar{
  width:var(--sidebar);flex-shrink:0;
  background:var(--surface);
  border-right:1px solid var(--line);
  overflow-y:auto;padding:.7rem 0;
  display:flex;flex-direction:column;
}
.nav{padding:0 .6rem .6rem;border-bottom:1px solid var(--line);margin-bottom:.5rem;display:flex;flex-direction:column;gap:.2rem}
.nav-item{
  display:flex;align-items:center;gap:.55rem;
  padding:.5rem .7rem;border-radius:8px;cursor:pointer;
  font-size:.83rem;font-weight:600;color:var(--muted);
  transition:all .15s;user-select:none;
}
.nav-item:hover{color:var(--text);background:var(--glass)}
.nav-item.active{color:var(--text);background:var(--violet-soft);border:1px solid rgba(139,92,246,.3)}
.nav-num{margin-left:auto;font-family:var(--font-mono);font-size:.68rem;padding:.1rem .45rem;border-radius:99px;background:rgba(255,255,255,.07);color:var(--muted)}
.nav-item.active .nav-num{background:var(--violet);color:#fff}

.sidebar-hdr{
  display:flex;align-items:center;justify-content:space-between;
  padding:.4rem 1rem .6rem;border-bottom:1px solid var(--line);
  margin-bottom:.5rem;
}
.sidebar-title{font-size:.64rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:var(--faint)}
.toggle-all-btn{background:none;border:none;color:var(--cyan);font-size:.72rem;cursor:pointer;font-weight:600;padding:.2rem .4rem;border-radius:4px}
.toggle-all-btn:hover{background:var(--cyan-soft)}

.cat-group{margin-bottom:.1rem}
.cat-parent{
  display:flex;align-items:center;gap:.5rem;
  padding:.44rem 1rem;cursor:pointer;
  font-size:.82rem;font-weight:500;color:var(--muted);
  transition:all .15s;border-left:3px solid transparent;user-select:none;
}
.cat-parent:hover{color:var(--text);background:var(--glass)}
.cat-parent.active{color:var(--cyan);border-left-color:var(--cyan);background:var(--cyan-soft)}
.cat-parent .arrow{margin-left:auto;font-size:.65rem;transition:transform .2s;color:var(--faint)}
.cat-parent.open .arrow{transform:rotate(90deg)}
.cat-num{font-size:.68rem;padding:.12rem .45rem;border-radius:99px;background:rgba(255,255,255,.06);color:var(--muted);font-family:var(--font-mono);margin-left:auto}
.cat-parent.active .cat-num{background:rgba(34,211,238,.2);color:var(--cyan)}
.cat-children{display:none;padding:0 0 .2rem 1.1rem}
.cat-group.expanded .cat-children{display:block}
.cat-child{
  display:flex;align-items:center;justify-content:space-between;
  padding:.3rem .8rem;cursor:pointer;font-size:.77rem;color:var(--muted);
  border-radius:6px;transition:all .15s;margin:.08rem 0;
}
.cat-child:hover{color:var(--text);background:var(--glass)}
.cat-child.active{color:var(--violet);background:var(--violet-soft)}
.cat-child.active .cat-num{background:rgba(139,92,246,.25);color:#c4b5fd}

/* CONTENT */
.content{flex:1;overflow-y:auto;padding:1.25rem 1.4rem}
.view{display:none}
.view.show{display:block;animation:fadeIn .25s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.section-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;gap:.8rem;flex-wrap:wrap}
.section-title-wrap{display:flex;align-items:center;gap:.6rem}
.section-hdr h2{font-family:var(--font-display);font-size:1.05rem;font-weight:600;color:var(--text)}
.section-hdr .sub{font-size:.72rem;color:var(--faint);font-weight:500}
.count-chip{font-size:.72rem;padding:.18rem .6rem;border-radius:99px;background:var(--violet-soft);color:#c4b5fd;font-weight:600;font-family:var(--font-mono)}

/* PRODUCT GRID */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:.8rem}
.card{
  background:var(--glass);border:1px solid var(--line);border-radius:var(--radius);
  cursor:pointer;transition:all .2s cubic-bezier(.4,0,.2,1);
  display:flex;flex-direction:column;overflow:hidden;position:relative;
}
.card::before{
  content:'';position:absolute;inset:0;border-radius:var(--radius);
  background:linear-gradient(135deg,rgba(139,92,246,.12),rgba(34,211,238,.05));
  opacity:0;transition:opacity .2s;pointer-events:none;z-index:1;
}
.card:hover{transform:translateY(-4px);box-shadow:0 16px 32px -12px rgba(139,92,246,.4);border-color:rgba(139,92,246,.45)}
.card:hover::before{opacity:1}
.card-img-wrap{
  padding:.6rem;background:rgba(255,255,255,.97);
  border-radius:calc(var(--radius) - 2px) calc(var(--radius) - 2px) 0 0;height:118px;
  display:flex;align-items:center;justify-content:center;position:relative;
}
.card-img{max-width:100%;max-height:102px;object-fit:contain}
.card-img-wrap.out::after{
  content:'';position:absolute;inset:0;background:rgba(10,10,18,.45);
  backdrop-filter:grayscale(1);
}
.heart{
  position:absolute;bottom:8px;right:8px;z-index:3;width:26px;height:26px;
  border-radius:50%;border:1px solid var(--line2);background:rgba(11,11,20,.55);
  backdrop-filter:blur(4px);color:var(--muted);cursor:pointer;font-size:.8rem;
  display:flex;align-items:center;justify-content:center;transition:all .15s;padding:0;line-height:1;
}
.heart:hover{color:var(--down);border-color:var(--down)}
.heart.on{color:var(--down);border-color:var(--down);background:var(--down-soft)}
.card-body{padding:.65rem;flex:1;display:flex;flex-direction:column;gap:.35rem;position:relative;z-index:2}
.card-name{font-size:.75rem;font-weight:500;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card-cat{font-size:.62rem;color:var(--faint);text-transform:uppercase;letter-spacing:.05em;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card-foot{display:flex;align-items:center;justify-content:space-between;margin-top:auto;padding-top:.15rem;gap:.3rem}
.price{
  font-family:var(--font-mono);font-size:.92rem;font-weight:700;font-variant-numeric:tabular-nums;
  background:linear-gradient(120deg,#c4b5fd,var(--cyan));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;white-space:nowrap;
}
.original-price{font-family:var(--font-mono);font-size:.64rem;color:var(--faint);text-decoration:line-through}
.badges{position:absolute;top:6px;left:6px;right:6px;z-index:2;display:flex;gap:.3rem;flex-wrap:wrap}
.badge{padding:.14rem .45rem;border-radius:99px;font-size:.62rem;font-weight:700;font-family:var(--font-mono)}
.badge-disc{background:var(--down);color:#fff;box-shadow:0 3px 8px rgba(251,113,133,.35);margin-left:auto}
.badge-atl{background:var(--gold);color:#1a1204;box-shadow:0 0 12px rgba(251,191,36,.55);animation:pulse 2.4s ease-in-out infinite}
.badge-alert{background:var(--cyan);color:#05222a}
@keyframes pulse{0%,100%{box-shadow:0 0 8px rgba(251,191,36,.4)}50%{box-shadow:0 0 18px rgba(251,191,36,.85)}}
.badge-out{background:rgba(100,116,139,.35);color:var(--muted2,#94a3b8)}
.drop-chip{display:inline-flex;align-items:center;gap:.25rem;font-family:var(--font-mono);font-size:.62rem;font-weight:600;color:var(--up)}
.stock-dot{width:6px;height:6px;border-radius:50%;display:inline-block;margin-right:.3rem}
.stock-dot.in{background:var(--up);box-shadow:0 0 6px rgba(52,211,153,.6)}
.stock-dot.out{background:var(--faint)}
.unit-tip{font-size:.63rem;color:var(--cyan);font-weight:600;font-family:var(--font-mono)}
.sale-chip{display:inline-block;font-family:var(--font-mono);font-size:.62rem;color:var(--down);font-weight:600}

/* LIST VIEW */
.list{display:flex;flex-direction:column;gap:.5rem}
.lrow{
  display:flex;align-items:center;gap:1rem;
  background:var(--glass);border:1px solid var(--line);border-radius:10px;
  padding:.55rem .8rem;cursor:pointer;transition:all .15s;position:relative;
}
.lrow:hover{background:var(--surface2);border-color:var(--line2);transform:translateX(2px)}
.lthumb{width:44px;height:44px;background:#fff;border-radius:6px;padding:3px;object-fit:contain;flex-shrink:0}
.lname{flex:1;min-width:0}
.lname b{font-size:.8rem;font-weight:600;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lname span{font-size:.66rem;color:var(--faint);text-transform:uppercase;letter-spacing:.05em}
.lprice{font-family:var(--font-mono);font-size:.85rem;font-weight:700;color:var(--text);font-variant-numeric:tabular-nums;white-space:nowrap}
.lprice small{display:block;font-size:.62rem;font-weight:500;color:var(--muted)}
.lstat{width:60px;text-align:right;font-family:var(--font-mono);font-size:.72rem;font-weight:600;white-space:nowrap}
.lstat .down{color:var(--down)}
.lstat .up{color:var(--up)}
.lstat .none{color:var(--faint)}

/* PAGINATION */
.pager{display:flex;justify-content:center;gap:.4rem;padding:1rem 0 0}
.pager-btn{padding:.35rem .75rem;background:var(--surface2);border:1px solid var(--line);border-radius:6px;color:var(--muted);cursor:pointer;font-size:.8rem;transition:all .15s;font-family:var(--font-mono)}
.pager-btn:hover,.pager-btn.active{background:var(--violet);color:#fff;border-color:var(--violet)}
.pager-btn:disabled{opacity:.35;cursor:not-allowed}

/* EMPTY / LOADING */
.empty{grid-column:1/-1;text-align:center;padding:4rem 2rem;color:var(--muted);display:flex;flex-direction:column;align-items:center;gap:1rem}
.empty-icon{font-size:2.6rem;opacity:.4}
.empty-msg{font-size:.95rem;font-weight:500}
.empty-sub{font-size:.8rem;color:var(--faint)}
.empty .btn{background:var(--violet);color:#fff;border:none;padding:.5rem 1.1rem;border-radius:8px;cursor:pointer;font-weight:600;font-size:.82rem}
.empty .btn:hover{background:#7c3aed}

/* ANALYTICS */
.ticker{
  overflow:hidden;border:1px solid var(--line);border-radius:10px;
  background:var(--surface);margin-bottom:1rem;position:relative;
}
.ticker::before,.ticker::after{content:'';position:absolute;top:0;bottom:0;width:60px;z-index:2;pointer-events:none}
.ticker::before{left:0;background:linear-gradient(90deg,var(--surface),transparent)}
.ticker::after{right:0;background:linear-gradient(-90deg,var(--surface),transparent)}
.ticker-track{display:inline-flex;gap:.4rem;padding:.45rem .9rem;white-space:nowrap;animation:tick 42s linear infinite}
.ticker:hover .ticker-track{animation-play-state:paused}
@keyframes tick{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
.tick{display:inline-flex;gap:.4rem;align-items:baseline;background:var(--surface2);border:1px solid var(--line);border-radius:99px;padding:.18rem .65rem;font-size:.7rem;color:var(--muted);font-family:var(--font-mono)}
.tick b{color:var(--text);font-weight:600;max-width:150px;overflow:hidden;text-overflow:ellipsis;font-family:var(--font-body)}
.tick em{color:var(--up);font-style:normal;font-weight:700}
.tick .bk{color:var(--faint)}

.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.75rem;margin-bottom:1rem}
.kpi{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  padding:.85rem .95rem;position:relative;overflow:hidden;transition:border-color .2s;
}
.kpi:hover{border-color:var(--line2)}
.kpi::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;border-radius:2px;background:var(--violet)}
.kpi.gold::before{background:var(--gold)}
.kpi.cyan::before{background:var(--cyan)}
.kpi.green::before{background:var(--up)}
.kpi-label{font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;color:var(--faint);font-weight:600}
.kpi-val{font-family:var(--font-mono);font-size:1.45rem;font-weight:700;margin-top:.2rem;font-variant-numeric:tabular-nums;color:var(--text)}
.kpi-val small{font-size:.8rem;color:var(--muted);font-weight:500}
.kpi-sub{font-size:.66rem;color:var(--faint);margin-top:.1rem}
.kpi .glow{position:absolute;right:-20px;top:-20px;width:80px;height:80px;border-radius:50%;filter:blur(30px);opacity:.35;background:var(--violet);pointer-events:none}

.panel{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);
  padding:1rem 1.05rem;margin-bottom:1rem;
}
.panel-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:.8rem;gap:.6rem}
.panel-hdr h3{font-family:var(--font-display);font-size:.92rem;font-weight:600;color:var(--text)}
.panel-hdr .cnt{font-family:var(--font-mono);font-size:.66rem;color:var(--faint);background:rgba(255,255,255,.05);padding:.12rem .5rem;border-radius:99px}
.analytics-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:1rem}

.dtable{width:100%;border-collapse:collapse}
.dtable th{
  text-align:left;font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;
  color:var(--faint);font-weight:600;padding:.35rem .4rem;border-bottom:1px solid var(--line);
}
.dtable td{padding:.45rem .4rem;border-bottom:1px solid rgba(255,255,255,.04);font-size:.78rem;vertical-align:middle}
.dtable tr{transition:background .12s}
.dtable tbody tr{cursor:pointer}
.dtable tbody tr:hover{background:var(--glass)}
.dtable .pcell{display:flex;align-items:center;gap:.5rem;min-width:0}
.dtable .pcell img{width:30px;height:30px;border-radius:5px;background:#fff;padding:2px;object-fit:contain;flex-shrink:0}
.dtable .pcell div{min-width:0}
.dtable .pcell b{display:block;font-size:.74rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:210px}
.dtable .pcell span{font-size:.6rem;color:var(--faint);text-transform:uppercase}
.dtable td.num,.dtable th.num{text-align:right;font-family:var(--font-mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.dtable .up{color:var(--up)}.dtable .down{color:var(--down)}.dtable .gold{color:var(--gold)}
.dtable .faint{color:var(--faint)}
.rank{font-family:var(--font-mono);color:var(--faint);font-size:.72rem;width:22px;display:inline-block;text-align:right}

.cat-wrap{display:grid;grid-template-columns:1fr 1fr;gap:1rem;align-items:center}
.cat-legend{display:flex;flex-direction:column;gap:.35rem;max-height:230px;overflow-y:auto;padding-right:.3rem}
.cat-legend .lg{display:flex;align-items:center;gap:.5rem;font-size:.72rem;color:var(--muted);cursor:pointer}
.cat-legend .lg:hover{color:var(--text)}
.cat-legend .dot{width:9px;height:9px;border-radius:3px;flex-shrink:0}
.cat-legend .lg b{margin-left:auto;font-family:var(--font-mono);color:var(--text)}
.cat-legend .lg span{font-family:var(--font-mono);color:var(--faint);font-size:.62rem}

/* WATCHLIST */
.watch-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:.8rem}
.wcard{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
  padding:.8rem;display:flex;flex-direction:column;gap:.6rem;transition:all .2s;
}
.wcard:hover{border-color:var(--line2)}
.wtop{display:flex;gap:.7rem;cursor:pointer;min-width:0}
.wtop img{width:48px;height:48px;background:#fff;border-radius:8px;padding:3px;object-fit:contain;flex-shrink:0}
.wtop b{display:block;font-size:.78rem;font-weight:600;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.wtop span{font-size:.62rem;color:var(--faint);text-transform:uppercase}
.wstats{display:flex;gap:.5rem;justify-content:space-between;align-items:flex-end}
.wprices{display:flex;flex-direction:column}
.wprices .now{font-family:var(--font-mono);font-size:1.05rem;font-weight:700;color:var(--text)}
.wprices .hilo{font-family:var(--font-mono);font-size:.64rem;color:var(--muted)}
.spark-wrap{height:44px;position:relative;flex:1;max-width:130px}
.alert-ctls{display:flex;gap:.4rem;align-items:center}
.alert-ctls input{
  width:90px;padding:.35rem .5rem;background:var(--surface2);border:1px solid var(--line);
  border-radius:6px;color:var(--text);font-size:.72rem;font-family:var(--font-mono);outline:none;
}
.alert-ctls input:focus{border-color:var(--cyan)}
.alert-ctls button{
  padding:.35rem .6rem;background:var(--cyan-soft);border:1px solid rgba(34,211,238,.3);
  color:var(--cyan);border-radius:6px;cursor:pointer;font-size:.7rem;font-weight:600;
}
.alert-ctls button:hover{background:var(--cyan);color:#04222b}
.alert-reached{font-size:.7rem;color:var(--up);font-weight:700;font-family:var(--font-mono);animation:pulse 2.4s infinite}
.alerts-panel .panel-body{display:flex;flex-direction:column;gap:.4rem}
.alert-row{display:flex;align-items:center;gap:.6rem;padding:.5rem .7rem;background:var(--surface2);border:1px solid var(--line);border-radius:8px;font-size:.76rem;cursor:pointer}
.alert-row:hover{border-color:var(--line2)}
.alert-row .ar-target{font-family:var(--font-mono);color:var(--cyan);font-weight:600}
.alert-row .ar-now{font-family:var(--font-mono);color:var(--text);font-weight:600}
.alert-row .ar-badge{font-family:var(--font-mono);font-size:.62rem;font-weight:700;padding:.15rem .5rem;border-radius:99px;background:var(--up-soft);color:var(--up);margin-left:auto}
.alert-row .ar-badge.wait{background:rgba(255,255,255,.06);color:var(--faint)}
.alert-row button{background:none;border:none;color:var(--faint);cursor:pointer;font-size:.85rem;padding:.1rem .3rem}
.alert-row button:hover{color:var(--down)}

/* MODAL (SteamDB-style) */
.overlay{
  position:fixed;inset:0;z-index:500;
  background:rgba(0,0,0,.82);backdrop-filter:blur(14px);
  display:flex;align-items:center;justify-content:center;
  opacity:0;pointer-events:none;transition:opacity .25s;
}
.overlay.show{opacity:1;pointer-events:auto}
.modal{
  background:var(--surface);border:1px solid var(--line2);
  border-radius:18px;width:min(96vw,1120px);height:min(92vh,780px);
  display:flex;flex-direction:column;
  transform:scale(.96) translateY(20px);
  transition:transform .25s cubic-bezier(.4,0,.2,1);
  box-shadow:0 40px 80px -20px rgba(0,0,0,.85),0 0 0 1px rgba(139,92,246,.22);
  overflow:hidden;
}
.overlay.show .modal{transform:scale(1) translateY(0)}
.modal-hdr{padding:1rem 1.25rem;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:.9rem;flex-shrink:0}
.modal-thumb{width:58px;height:58px;object-fit:contain;background:#fff;border-radius:8px;padding:4px;flex-shrink:0}
.modal-meta{flex:1;min-width:0}
.modal-title{font-size:1rem;font-weight:600;line-height:1.3;margin-bottom:.2rem}
.modal-sub{font-size:.72rem;color:var(--muted);font-family:var(--font-mono)}
.close-btn{background:var(--surface2);border:1px solid var(--line);color:var(--muted);border-radius:8px;width:32px;height:32px;cursor:pointer;font-size:1rem;flex-shrink:0;display:flex;align-items:center;justify-content:center;transition:all .15s}
.close-btn:hover{background:var(--glass);color:var(--text)}
.modal-body{flex:1;min-height:0;padding:1.1rem 1.25rem;display:flex;flex-direction:column;gap:.9rem;overflow:hidden}

.pstats{display:grid;grid-template-columns:repeat(6,1fr);gap:.6rem;flex-shrink:0}
.pstat{background:var(--surface2);border:1px solid var(--line);border-radius:10px;padding:.6rem .75rem;display:flex;flex-direction:column;gap:.15rem}
.pstat-label{font-size:.56rem;text-transform:uppercase;letter-spacing:.08em;color:var(--faint);font-weight:600;white-space:nowrap}
.pstat-val{font-family:var(--font-mono);font-size:1.02rem;font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}
.pstat-val.curr{color:var(--text)}
.pstat-val.low{color:var(--up)}
.pstat-val.high{color:var(--down)}
.pstat-val.gold{color:var(--gold)}
.pstat-val.unit{color:var(--cyan);font-size:.88rem}

.alert-bar{
  display:none;flex-shrink:0;
  background:var(--gold-soft);border:1px solid rgba(251,191,36,.3);
  border-radius:8px;padding:.55rem .95rem;color:var(--gold);
  font-weight:600;font-size:.8rem;align-items:center;gap:.6rem;
}
.alert-bar.deal{background:var(--up-soft);border-color:rgba(52,211,153,.3);color:var(--up)}
.alert-bar.show{display:flex}

.ctl-row{display:flex;align-items:center;gap:.6rem;flex-shrink:0;flex-wrap:wrap}
.seg{display:flex;gap:.25rem;background:var(--surface2);border:1px solid var(--line);border-radius:8px;padding:.22rem}
.seg button{
  background:none;border:none;color:var(--muted);font-size:.72rem;font-weight:600;
  padding:.32rem .7rem;border-radius:6px;cursor:pointer;transition:all .15s;font-family:var(--font-mono);
}
.seg button:hover{color:var(--text)}
.seg button.active{background:var(--violet);color:#fff;box-shadow:0 2px 10px rgba(139,92,246,.4)}
.seg.cyan button.active{background:var(--cyan);color:#04222b}
.ctl-label{font-size:.66rem;text-transform:uppercase;letter-spacing:.1em;color:var(--faint);font-weight:600}
.chart-legend{display:flex;gap:.9rem;align-items:center;font-size:.68rem;color:var(--muted);font-family:var(--font-mono);flex-wrap:wrap}
.chart-legend .cl{display:flex;align-items:center;gap:.3rem}
.chart-legend .sw{width:16px;height:3px;border-radius:2px;display:inline-block}
.chart-legend .dot{width:7px;height:7px;border-radius:50%}
.chart-wrap{flex:1;min-height:0;width:100%;height:100%;position:relative}

.alert-ctl{display:flex;align-items:center;gap:.5rem;flex-shrink:0;flex-wrap:wrap}
.alert-ctl input{
  width:120px;padding:.4rem .55rem;background:var(--surface2);border:1px solid var(--line);
  border-radius:7px;color:var(--text);font-size:.76rem;font-family:var(--font-mono);outline:none;
}
.alert-ctl input:focus{border-color:var(--cyan)}
.alert-ctl button{
  padding:.4rem .8rem;background:var(--cyan-soft);border:1px solid rgba(34,211,238,.35);
  color:var(--cyan);border-radius:7px;cursor:pointer;font-size:.74rem;font-weight:600;transition:all .15s;
}
.alert-ctl button:hover{background:var(--cyan);color:#04222b}
.alert-ctl button.danger{background:var(--down-soft);border-color:rgba(251,113,133,.35);color:var(--down)}
.alert-ctl button.danger:hover{background:var(--down);color:#2b080f}
.alert-status{font-family:var(--font-mono);font-size:.7rem;font-weight:600}
.alert-status .hit{color:var(--up)}
.alert-status .set{color:var(--cyan)}
.alert-status .off{color:var(--faint)}

/* RESPONSIVE */
@media (max-width:1000px){
  .pstats{grid-template-columns:repeat(3,1fr)}
  .cat-wrap{grid-template-columns:1fr}
  .header-stats .hstat:nth-child(n+4){display:none}
}
@media (max-width:820px){
  .menu-btn{display:flex;align-items:center;justify-content:center}
  .sidebar{position:fixed;left:0;top:57px;bottom:0;z-index:400;width:266px;transform:translateX(-105%);transition:transform .25s;box-shadow:30px 0 60px rgba(0,0,0,.5)}
  .sidebar.open{transform:none}
  .layout{height:calc(100vh - 57px)}
  .header-stats .hstat:nth-child(n+3){display:none}
  .search-wrap{width:150px}
  .content{padding:1rem}
}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation:none!important;transition:none!important}
}
</style>
</head>
<body>

<!-- HEADER -->
<header class="header">
  <button class="menu-btn" onclick="document.querySelector('.sidebar').classList.toggle('open')">☰</button>
  <div class="logo">Pickaboo<span class="tick">Price Intelligence Terminal</span></div>
  <div class="header-stats">
    <div class="hstat"><span class="hstat-label">Products</span><span class="hstat-val" id="hProducts">—</span></div>
    <div class="hstat"><span class="hstat-label">Categories</span><span class="hstat-val" id="hCats">—</span></div>
    <div class="hstat"><span class="hstat-label">Snapshots</span><span class="hstat-val" id="hRecords">—</span></div>
    <div class="hstat"><span class="hstat-label">Days tracked</span><span class="hstat-val" id="hDays">—</span></div>
    <div class="hstat"><span class="hstat-label">All-time lows</span><span class="hstat-val" id="hAtl">—</span></div>
  </div>
  <div class="spacer"></div>
  <div class="controls-wrap">
    <button class="tbtn atl" id="atlBtn" onclick="toggleFilter('atl')">📉 ATL</button>
    <button class="tbtn sale" id="saleBtn" onclick="toggleFilter('sale')">🔥 Deals</button>
    <button class="tbtn stock" id="stockBtn" onclick="toggleFilter('stock')">◉ In stock</button>
    <button class="tbtn" id="viewBtn" onclick="toggleListView()" title="Toggle list view">≡</button>
    <div class="search-wrap">
      <span class="ico">⌕</span>
      <input type="text" id="searchBox" placeholder="Search products…" oninput="debounce()">
    </div>
    <select class="sort-sel" id="sortSel" onchange="loadProducts(1)">
      <option value="newest">Newest</option>
      <option value="price_asc">Price: low → high</option>
      <option value="price_desc">Price: high → low</option>
      <option value="discount">Discount %</option>
      <option value="drop">Biggest drop from peak</option>
    </select>
  </div>
</header>

<!-- LAYOUT -->
<div class="layout">
  <aside class="sidebar" id="sidebar">
    <div class="nav">
      <div class="nav-item active" data-view="browse" onclick="setView('browse')"><span>🛍️</span> Browse</div>
      <div class="nav-item" data-view="analytics" onclick="setView('analytics')"><span>📊</span> Analytics</div>
      <div class="nav-item" data-view="watch" onclick="setView('watch')"><span>🔔</span> Watchlist<span class="nav-num" id="watchCount">0</span></div>
    </div>
    <div class="sidebar-hdr">
      <span class="sidebar-title">Categories</span>
      <button class="toggle-all-btn" onclick="toggleExpandAll()">Expand All</button>
    </div>
    <div class="cat-group">
      <div class="cat-parent active" id="cat-all" onclick="selectCat('','All Products',this)">
        <span>🏠 All Products</span>
        <span class="cat-num" id="cat-all-num">0</span>
      </div>
    </div>
    <div id="catTree"></div>
  </aside>

  <main class="content" onclick="document.getElementById('sidebar').classList.remove('open')">
    <!-- BROWSE -->
    <section class="view show" id="view-browse">
      <div class="section-hdr">
        <div class="section-title-wrap">
          <h2 id="sectionTitle">All Products</h2>
          <span class="count-chip" id="countChip">0 items</span>
        </div>
        <span class="sub" id="sectionSub">last scrape · —</span>
      </div>
      <div class="grid" id="grid"></div>
      <div class="pager" id="pager"></div>
    </section>

    <!-- ANALYTICS -->
    <section class="view" id="view-analytics">
      <div class="ticker"><div class="ticker-track" id="tickerTrack"></div></div>
      <div class="kpis" id="kpis"></div>
      <div class="analytics-grid">
        <div class="panel">
          <div class="panel-hdr"><h3>Biggest drops from peak</h3><span class="cnt">% below all-time high</span></div>
          <table class="dtable"><thead><tr><th></th><th>Product</th><th class="num">Now</th><th class="num">Peak</th><th class="num">Drop</th></tr></thead><tbody id="dropsBody"></tbody></table>
        </div>
        <div class="panel">
          <div class="panel-hdr"><h3>Hottest discounts right now</h3><span class="cnt">current sale %</span></div>
          <table class="dtable"><thead><tr><th></th><th>Product</th><th class="num">Now</th><th class="num">Was</th><th class="num">%</th></tr></thead><tbody id="discBody"></tbody></table>
        </div>
      </div>
      <div class="analytics-grid">
        <div class="panel">
          <div class="panel-hdr"><h3>Catalog by category</h3><span class="cnt">top tracked categories</span></div>
          <div class="cat-wrap">
            <div class="chart-wrap" style="height:250px"><canvas id="catDonut"></canvas></div>
            <div class="cat-legend" id="catLegend"></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-hdr"><h3>All-time lows right now</h3><span class="cnt">sitting at lowest ever</span></div>
          <table class="dtable"><thead><tr><th></th><th>Product</th><th class="num">Now</th><th class="num">Avg</th><th class="num">vs avg</th></tr></thead><tbody id="atlBody"></tbody></table>
        </div>
      </div>
    </section>

    <!-- WATCHLIST -->
    <section class="view" id="view-watch">
      <div class="section-hdr">
        <div class="section-title-wrap">
          <h2>Watchlist</h2>
          <span class="count-chip" id="watchChip">0 items</span>
        </div>
        <span class="sub">Saved on this browser · price alerts fire when target is reached</span>
      </div>
      <div class="panel alerts-panel" id="alertsPanel">
        <div class="panel-hdr"><h3>🔔 Active price alerts</h3><span class="cnt">target hit = green</span></div>
        <div class="panel-body" id="alertsBody"></div>
      </div>
      <div class="watch-grid" id="watchList"></div>
    </section>
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
        <div class="pstat"><div class="pstat-label">Current</div><div class="pstat-val curr" id="mCurr">—</div></div>
        <div class="pstat"><div class="pstat-label">Lowest ever</div><div class="pstat-val low" id="mLow">—</div></div>
        <div class="pstat"><div class="pstat-label">Highest ever</div><div class="pstat-val high" id="mHigh">—</div></div>
        <div class="pstat"><div class="pstat-label">Average</div><div class="pstat-val gold" id="mAvg">—</div></div>
        <div class="pstat"><div class="pstat-label">Vs average</div><div class="pstat-val curr" id="mVs">—</div></div>
        <div class="pstat"><div class="pstat-label">Best discount</div><div class="pstat-val unit" id="mDisc">—</div></div>
      </div>
      <div class="alert-bar" id="alertBar"><span>🔥</span><span id="alertMsg"></span></div>
      <div class="ctl-row">
        <div class="seg" id="rangeSeg">
          <button data-r="7d" onclick="setRange('7d')">1W</button>
          <button data-r="30d" onclick="setRange('30d')">1M</button>
          <button data-r="90d" onclick="setRange('90d')">3M</button>
          <button data-r="all" class="active" onclick="setRange('all')">ALL</button>
        </div>
        <div class="seg cyan" id="metricSeg">
          <button data-m="price" class="active" onclick="setMetric('price')">Price</button>
          <button data-m="discount" onclick="setMetric('discount')">Discount %</button>
        </div>
        <span class="ctl-label" id="mUnitLbl"></span>
        <div class="chart-legend" id="chartLegend"></div>
      </div>
      <div class="chart-wrap"><canvas id="priceChart"></canvas></div>
      <div class="alert-ctl">
        <span class="ctl-label">🔔 Alert me below</span>
        <input type="number" id="alertTarget" placeholder="৳ 0" min="0" step="1">
        <button id="alertSetBtn" onclick="setAlert()">Set alert</button>
        <button class="danger" id="alertClearBtn" onclick="clearAlert()">Clear</button>
        <span class="alert-status" id="alertStatus"></span>
      </div>
    </div>
  </div>
</div>

<script>
'use strict';
const $ = id => document.getElementById(id);
const money = n => '৳' + Math.round(n||0).toLocaleString();
const moneyShort = n => n>=100000 ? '৳'+(n/100000).toFixed(1)+'L' : money(n);
const effOf = r => (r.special_price>0 ? r.special_price : r.price);
const esc = s => (s||'').replace(/'/g,"\\'").replace(/"/g,'\\"');
const parseDate = s => {
  if(!s) return null;
  const d = new Date(String(s).trim().replace(' ','T'));
  return isNaN(d) ? null : d;
};
const fmtDate = s => {
  const d = parseDate(s);
  if(!d) return (s||'—');
  const o = d.toLocaleDateString('en-GB',{day:'numeric',month:'short'});
  return isNaN(d) ? (s||'—') : o;
};
const fmtDateTime = s => {
  const d = parseDate(s);
  if(!d) return (s||'—');
  return d.toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
};

let state = { view:'browse', curCat:'', search:'', sort:'newest', page:1, totalPages:1,
              atl:false, sale:false, stock:false, listView:false, allExpanded:false };
let watchlist = JSON.parse(localStorage.getItem('pb_watch')||'[]');
let alerts = JSON.parse(localStorage.getItem('pb_alerts')||'{}');
let chart = null, donut = null, sparkCharts = [];
let curHistory = [], curProduct = null;
let chartRange = 'all', chartMetric = 'price';

// ── INIT ───────────────────────────────────────────────────────────────────────
async function init(){
  await Promise.all([loadStats(), loadCats()]);
  renderWatchCount();
  loadProducts(1);
}

async function api(url){
  try{ const r = await fetch(url); return await r.json(); }
  catch(e){ console.error(url, e); return {}; }
}

// ── STATS ──────────────────────────────────────────────────────────────────────
async function loadStats(){
  const d = await api('/api/stats');
  $('hProducts').textContent = (d.total_products||0).toLocaleString();
  $('hCats').textContent = (d.total_cats||0).toLocaleString();
  $('hRecords').textContent = (d.total_records||0).toLocaleString();
  $('hDays').textContent = d.days_span||'—';
  $('hAtl').textContent = (d.atl_count||0).toLocaleString();
  $('cat-all-num').textContent = (d.total_products||0).toLocaleString();
  $('sectionSub').textContent = 'last scrape · ' + fmtDateTime(d.last_scraped);
}

// ── CATEGORIES ─────────────────────────────────────────────────────────────────
async function loadCats(){
  const cats = await api('/api/categories');
  const tree = $('catTree');
  tree.innerHTML='';
  const parents = cats.filter(c=>!c.parent_id);
  const childMap = {};
  cats.filter(c=>c.parent_id).forEach(c=>{ (childMap[c.parent_id]=childMap[c.parent_id]||[]).push(c); });

  parents.forEach(p=>{
    const group = document.createElement('div');
    group.className = 'cat-group';
    const children = childMap[p.id]||[];
    const hasChildren = children.length>0;
    const childSum = children.reduce((s,c)=> s + (c.prod_count||0), 0);
    const total = (p.prod_count||0) + childSum;
    group.innerHTML = `
      <div class="cat-parent" onclick="handleParentClick('${p.id}','${esc(p.name)}',this)">
        <span>${p.name}</span>
        ${hasChildren?'<span class="arrow">›</span>':''}
        <span class="cat-num">${total}</span>
      </div>
      ${hasChildren?`<div class="cat-children">
        ${children.map(c=>`
          <div class="cat-child" onclick="selectCat('${c.id}','${esc(c.name)}',this)">
            <span>${c.name}</span>
            <span class="cat-num">${c.prod_count||0}</span>
          </div>`).join('')}
      </div>`:''}`;
    tree.appendChild(group);
  });
}

function handleParentClick(id,name,el){
  const group = el.closest('.cat-group');
  if(group.querySelector('.cat-children')){ group.classList.toggle('expanded'); el.classList.toggle('open'); }
  selectCat(id,name,el);
}

function toggleExpandAll(){
  state.allExpanded = !state.allExpanded;
  document.querySelectorAll('.cat-group').forEach(g=>g.classList.toggle('expanded', state.allExpanded));
  document.querySelectorAll('.cat-parent').forEach(p=>p.classList.toggle('open', state.allExpanded));
  document.querySelector('.toggle-all-btn').textContent = state.allExpanded ? 'Collapse All' : 'Expand All';
}

function selectCat(id,name,el){
  state.curCat = id;
  document.querySelectorAll('.cat-parent,.cat-child').forEach(x=>x.classList.remove('active'));
  if(el) el.classList.add('active');
  $('sectionTitle').textContent = name || 'All Products';
  loadProducts(1);
}

// ── FILTERS / VIEWS ────────────────────────────────────────────────────────────
function toggleFilter(k){
  state[k] = !state[k];
  $(k==='atl'?'atlBtn':k==='sale'?'saleBtn':'stockBtn').classList.toggle('active', state[k]);
  loadProducts(1);
}

function toggleListView(){
  state.listView = !state.listView;
  $('viewBtn').classList.toggle('active', state.listView);
  loadProducts(state.page);
}

function setView(v){
  state.view = v;
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active', n.dataset.view===v));
  ['browse','analytics','watch'].forEach(x=>$('view-'+x).classList.toggle('show', x===v));
  destroyCharts();
  if(v==='analytics') loadAnalytics();
  if(v==='watch') loadWatchlist();
  if(v==='browse') loadProducts(1);
  document.querySelector('.content').scrollTop = 0;
  document.getElementById('sidebar').classList.remove('open');
}

function destroyCharts(){
  if(chart){ chart.destroy(); chart=null; }
  if(donut){ donut.destroy(); donut=null; }
  sparkCharts.forEach(c=>{ try{c.destroy();}catch(e){} });
  sparkCharts = [];
}

// ── PRODUCTS (browse) ──────────────────────────────────────────────────────────
async function loadProducts(page=1){
  if(state.view!=='browse') return;
  state.page = page;
  const grid = $('grid');
  grid.innerHTML = '<div class="empty"><div class="empty-icon">⏳</div><div class="empty-msg">Loading…</div></div>';

  const params = new URLSearchParams({
    category_id: state.curCat,
    search: state.search,
    sort: state.sort,
    page,
    atl: state.atl?1:0,
    sale: state.sale?1:0,
    stock: state.stock?1:0
  });
  const data = await api('/api/products?'+params);

  $('countChip').textContent = (data.total||0).toLocaleString() + ' items';
  state.totalPages = Math.ceil((data.total||0)/40);
  renderPager();
  grid.innerHTML='';

  if(!data.products || data.products.length===0){
    grid.innerHTML = `<div class="empty">
      <div class="empty-icon">📭</div>
      <div class="empty-msg">No products match these filters</div>
      <div class="empty-sub">Try clearing a filter, widening your search, or running a fresh scrape.</div>
    </div>`;
    return;
  }
  if(state.listView){
    const list = document.createElement('div');
    list.className = 'list';
    data.products.forEach(p=> list.appendChild(listRow(p)));
    grid.appendChild(list);
  } else {
    data.products.forEach(p=> grid.appendChild(card(p)));
  }
}

function heartBtn(p){
  const on = watchlist.includes(String(p.id));
  return `<button class="heart ${on?'on':''}" onclick="event.stopPropagation();toggleWatch('${p.id}',this)" title="${on?'Remove from watchlist':'Add to watchlist'}">${on?'♥':'♡'}</button>`;
}

function badgeHtml(p){
  const eff = p.eff;
  let b='';
  if(p.is_atl) b += '<span class="badge badge-atl">★ ATL</span>';
  if(alerts[String(p.id)] && eff<=alerts[String(p.id)]) b += '<span class="badge badge-alert">🔔 HIT</span>';
  if(p.discount>0) b += `<span class="badge badge-disc">−${Math.round(p.discount)}%</span>`;
  if(!p.stock_available) b += '<span class="badge badge-out">OUT</span>';
  return b;
}

function card(p){
  const d = document.createElement('div');
  d.className = 'card';
  d.onclick = ()=>openModal(p);
  d.innerHTML = `
    <div class="badges">${badgeHtml(p)}</div>
    <div class="card-img-wrap ${p.stock_available?'':'out'}">
      <img class="card-img" src="${p.product_img||''}" alt="${esc(p.name)}"
        onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><text y=%2250%25%22 x=%2250%25%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 font-size=%2224%22>📦</text></svg>'">
    </div>
    ${heartBtn(p)}
    <div class="card-body">
      <div class="card-name" title="${esc(p.name)}">${p.name}</div>
      <div class="card-cat">${p.category_name||''}</div>
      ${(p.unit&&p.unit_value)?`<div class="unit-tip">${moneyShort(effOf(p)/p.unit_value)} / ${p.unit}</div>`:''}
      <div class="card-foot">
        <div>
          <span class="stock-dot ${p.stock_available?'in':'out'}"></span>
          ${p.discount>0?`<span class="sale-chip">−${Math.round(p.discount)}%</span>`:''}
          ${(p.drop_pct&&p.drop_pct>=5)?`<span class="drop-chip">⌄ ${p.drop_pct}% peak</span>`:''}
        </div>
        <span class="price">${money(effOf(p))}</span>
      </div>
    </div>`;
  return d;
}

function listRow(p){
  const row = document.createElement('div');
  row.className = 'lrow';
  row.onclick = ()=>openModal(p);
  const isAtl = p.is_atl;
  const drop = p.drop_pct||0;
  row.innerHTML = `
    <img class="lthumb" src="${p.product_img||''}" alt="" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2240%22 height=%2240%22><text y=%2255%25%22 x=%2250%25%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 font-size=%2218%22>📦</text></svg>'">
    <div class="lname"><b>${p.name}</b><span>${p.category_name||''}${isAtl?' · ★ ATL':''}</span></div>
    <div class="lprice">${money(effOf(p))}${p.discount>0?`<small><s>${money(p.price)}</s> −${Math.round(p.discount)}%</small>`:''}</div>
    <div class="lstat ${drop>=5?'up':isAtl?'up':''}">${drop>=5?('⌄ '+drop+'%'):(isAtl?'★ ATL':'—')}</div>
    ${heartBtn(p)}`;
  return row;
}

function renderPager(){
  const pg = $('pager');
  pg.innerHTML='';
  if(state.totalPages<=1) return;
  const mk = (lbl,page,disabled,active)=>{
    const b = document.createElement('button');
    b.className='pager-btn'+(active?' active':'');
    b.textContent=lbl; b.disabled=disabled;
    b.onclick=()=>{ loadProducts(page); document.querySelector('.content').scrollTop=0; };
    return b;
  };
  pg.appendChild(mk('‹ Prev', state.page-1, state.page===1));
  const start = Math.max(1,state.page-2), end = Math.min(state.totalPages,state.page+2);
  for(let i=start;i<=end;i++) pg.appendChild(mk(i,i,false,i===state.page));
  pg.appendChild(mk('Next ›', state.page+1, state.page===state.totalPages));
}

// ── WATCHLIST ──────────────────────────────────────────────────────────────────
function renderWatchCount(){
  $('watchCount').textContent = watchlist.length;
  $('watchChip').textContent = watchlist.length + ' items';
}

function toggleWatch(id, el){
  id = String(id);
  const i = watchlist.indexOf(id);
  if(i>=0) watchlist.splice(i,1); else watchlist.push(id);
  localStorage.setItem('pb_watch', JSON.stringify(watchlist));
  if(el) el.innerHTML = watchlist.includes(id)?'♥':'♡', el.classList.toggle('on', watchlist.includes(id));
  renderWatchCount();
  if(state.view==='watch') loadWatchlist();
}

async function loadWatchlist(){
  const box = $('watchList');
  const alertsBody = $('alertsBody');
  alertsBody.innerHTML = '';
  box.innerHTML='';

  // alerts panel
  const alertIds = Object.keys(alerts);
  if(alertIds.length===0){
    alertsBody.innerHTML = '<div class="empty-sub" style="padding:.4rem">No alerts yet — open any product and set a target price.</div>';
  } else {
    for(const id of alertIds){
      const p = await api('/api/product/'+id);
      if(!p || !p.id) continue;
      const now = effOf(p);
      const hit = now <= alerts[id];
      const r = document.createElement('div');
      r.className = 'alert-row';
      r.onclick = ()=>openModal(p);
      r.innerHTML = `
        <img src="${p.product_img||''}" width="26" height="26" style="border-radius:4px;background:#fff;padding:1px;object-fit:contain" onerror="this.style.visibility='hidden'">
        <div style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.name}</div>
        <span class="ar-target">target ${money(alerts[id])}</span>
        <span class="ar-now">now ${money(now)}</span>
        <span class="ar-badge ${hit?'':'wait'}">${hit?'🔔 HIT':'waiting'}</span>
        <button onclick="event.stopPropagation();removeAlert('${id}')" title="Remove alert">✕</button>`;
      alertsBody.appendChild(r);
    }
  }

  // watched products
  if(watchlist.length===0){
    box.innerHTML = `<div class="empty">
      <div class="empty-icon">🔔</div>
      <div class="empty-msg">Your watchlist is empty</div>
      <div class="empty-sub">Tap the ♡ on any product card to track it here.</div>
    </div>`;
    return;
  }
  for(const id of watchlist){
    const p = await api('/api/product/'+id);
    if(!p || !p.id) continue;
    const h = (await api('/api/product/'+id+'/history')).history || [];
    box.appendChild(watchCard(p,h));
  }
}

function watchCard(p, h){
  const w = document.createElement('div');
  w.className = 'wcard';
  const prices = h.map(effOf);
  const low = prices.length?Math.min(...prices):null;
  const high = prices.length?Math.max(...prices):null;
  const now = effOf(p);
  const target = alerts[String(p.id)];
  const hit = target && now<=target;
  w.innerHTML = `
    <div class="wtop" onclick="openModal(p)">
      <img src="${p.product_img||''}" alt="" onerror="this.style.visibility='hidden'">
      <div>
        <b>${p.name}</b>
        <span>${p.category_name||''}${p.is_atl?' · ★ ATL':''}</span>
      </div>
    </div>
    <div class="wstats">
      <div class="wprices">
        <div class="now">${money(now)}</div>
        <div class="hilo">LOW ${money(low)} · HIGH ${money(high)}</div>
      </div>
      <div class="spark-wrap"><canvas data-spark></canvas></div>
    </div>
    <div class="alert-ctls">
      <input type="number" placeholder="৳ target" value="${target||''}" onchange="setAlertQuick('${p.id}',this.value)">
      ${hit?'<span class="alert-reached">🔔 TARGET HIT</span>':''}
    </div>`;
  const el = w.querySelector('[data-spark]');
  const g = el.getContext('2d');
  const grad = g.createLinearGradient(0,0,0,40);
  grad.addColorStop(0,'rgba(139,92,246,.5)'); grad.addColorStop(1,'rgba(139,92,246,0)');
  sparkCharts.push(new Chart(el, {
    type:'line',
    data:{ labels:prices.map((_,i)=>i), datasets:[{ data:prices, borderColor:'#8b5cf6', backgroundColor:grad, fill:true, tension:.4, borderWidth:1.8, pointRadius:0 }]},
    options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false},tooltip:{enabled:false}}, scales:{x:{display:false},y:{display:false}} }
  }));
  return w;
}

function setAlertQuick(id, val){
  const t = parseFloat(val);
  if(!t || t<=0){ removeAlert(id); return; }
  alerts[String(id)] = t;
  localStorage.setItem('pb_alerts', JSON.stringify(alerts));
  loadWatchlist();
}

function removeAlert(id){
  delete alerts[String(id)];
  localStorage.setItem('pb_alerts', JSON.stringify(alerts));
  loadWatchlist();
}

// ── ANALYTICS ──────────────────────────────────────────────────────────────────
function kpi(label, val, sub, cls){
  return `<div class="kpi ${cls||''}">
    <div class="glow"></div>
    <div class="kpi-label">${label}</div>
    <div class="kpi-val">${val}</div>
    ${sub?`<div class="kpi-sub">${sub}</div>`:''}
  </div>`;
}

async function loadAnalytics(){
  const d = await api('/api/analytics');
  const s = d.summary||{};
  const atlPct = s.total_products ? Math.round(s.atl_count/s.total_products*100) : 0;

  $('kpis').innerHTML =
    kpi('Products tracked', (s.total_products||0).toLocaleString(), 'catalog items', 'cyan') +
    kpi('Price snapshots', (s.total_records||0).toLocaleString(), 'historical records', '') +
    kpi('Data span', s.days_span||'—', (s.first_scraped||'').slice(0,10) + ' → ' + (s.last_scraped||'').slice(0,10), 'gold') +
    kpi('All-time lows now', (s.atl_count||0).toLocaleString(), `${atlPct}% of catalog`, 'green') +
    kpi('Average discount', (s.avg_discount||0)+'%', 'across current prices', '') +
    kpi('Avg current price', money(s.avg_price||0), 'mean of latest snapshots', 'cyan');

  // ticker
  const drops = d.top_drops||[];
  $('tickerTrack').innerHTML = drops.concat(drops).map(x=>`
    <span class="tick"><b>${x.name}</b><em>${money(x.eff)}</em><span class="bk">from ${money(x.hist_max)}</span><em>−${x.drop_pct}%</em></span>`).join('');

  // drops table
  $('dropsBody').innerHTML = drops.slice(0,8).map((x,i)=>`
    <tr onclick="openById('${x.id}')">
      <td><span class="rank">${i+1}</span></td>
      <td><div class="pcell"><img src="${x.product_img||''}" onerror="this.style.visibility='hidden'"><div><b>${x.name}</b><span>${x.category_name||''}</span></div></div></td>
      <td class="num up">${money(x.eff)}</td>
      <td class="num faint">${money(x.hist_max)}</td>
      <td class="num down">−${x.drop_pct}%</td>
    </tr>`).join('') || '<tr><td colspan="5" class="faint">Not enough history yet.</td></tr>';

  // discounts table
  $('discBody').innerHTML = (d.top_discounts||[]).slice(0,8).map((x,i)=>`
    <tr onclick="openById('${x.id}')">
      <td><span class="rank">${i+1}</span></td>
      <td><div class="pcell"><img src="${x.product_img||''}" onerror="this.style.visibility='hidden'"><div><b>${x.name}</b><span>${x.category_name||''}</span></div></div></td>
      <td class="num">${money(x.eff)}</td>
      <td class="num faint">${money(x.price)}</td>
      <td class="num gold">−${Math.round(x.discount)}%</td>
    </tr>`).join('') || '<tr><td colspan="5" class="faint">No active discounts.</td></tr>';

  // atl table
  $('atlBody').innerHTML = (d.atl_now||[]).slice(0,8).map((x,i)=>`
    <tr onclick="openById('${x.id}')">
      <td><span class="rank">${i+1}</span></td>
      <td><div class="pcell"><img src="${x.product_img||''}" onerror="this.style.visibility='hidden'"><div><b>${x.name}</b><span>${x.category_name||''}</span></div></div></td>
      <td class="num up">${money(x.eff)}</td>
      <td class="num faint">${money(x.hist_avg)}</td>
      <td class="num gold">${x.pct_below_avg>=0?'−':'+'+(Math.abs(x.pct_below_avg))}%</td>
    </tr>`).join('') || '<tr><td colspan="5" class="faint">No all-time lows right now.</td></tr>';

  renderCatDonut(d.category_dist||[]);
}

function renderCatDonut(dist){
  if(!dist.length) return;
  const ctx = $('catDonut').getContext('2d');
  const palette = ['#8b5cf6','#22d3ee','#fbbf24','#34d399','#fb7185','#a78bfa','#2dd4bf','#f472b6','#60a5fa','#f97316','#a3e635','#e879f9'];
  const labels = dist.map(c=>c.name);
  const data = dist.map(c=>c.cnt);
  const cols = dist.map((_,i)=>palette[i%palette.length]);
  donut = new Chart(ctx, {
    type:'doughnut',
    data:{ labels, datasets:[{ data, backgroundColor:cols, borderColor:'#0b0b14', borderWidth:2, hoverOffset:6 }]},
    options:{ responsive:true, maintainAspectRatio:false, cutout:'62%',
      plugins:{ legend:{display:false}, tooltip:{ backgroundColor:'rgba(11,11,20,.95)', borderColor:'rgba(255,255,255,.1)', borderWidth:1,
        callbacks:{ label: c => ` ${c.label}: ${c.parsed.toLocaleString()} products (avg disc ${dist[c.dataIndex].avg_discount}%)` } } } }
  });
  $('catLegend').innerHTML = dist.slice(0,10).map((c,i)=>`
    <div class="lg" onclick="donut.setActiveElements([{datasetIndex:0,index:${i}}]);donut.tooltip.setActiveElements([{datasetIndex:0,index:${i}}]);donut.update()">
      <span class="dot" style="background:${cols[i]}"></span>${c.name}<b>${c.cnt.toLocaleString()}</b><span>${c.avg_discount}%</span>
    </div>`).join('');
}

// ── MODAL / STEAMDB CHART ──────────────────────────────────────────────────────
async function openById(id){
  const p = await api('/api/product/'+id);
  if(p && p.id) openModal(p);
}

async function openModal(p){
  curProduct = p;
  $('mThumb').src = p.product_img||'';
  $('mTitle').textContent = p.name;
  $('mSub').textContent = `SKU ${p.sku||'—'}  ·  ${p.category_name||'—'}  ·  id ${p.id}`;
  $('overlay').classList.add('show');

  const data = await api(`/api/product/${p.id}/history`);
  curHistory = data.history||[];
  if(curHistory.length===0){
    ['mCurr','mLow','mHigh','mAvg','mVs','mDisc'].forEach(id=>$(id).textContent='—');
    $('chartLegend').innerHTML='';
    return;
  }
  renderModalStats(curProduct);
  renderAlertUi();
  renderSteam();
}

function renderModalStats(p){
  const prices = curHistory.map(effOf);
  const curr = prices[prices.length-1];
  const low = Math.min(...prices), high = Math.max(...prices);
  const avg = prices.reduce((a,b)=>a+b,0)/prices.length;
  const vs = avg>0 ? ((avg-curr)/avg*100) : 0;
  const maxDisc = Math.max(...curHistory.map(r=>r.discount||0));
  $('mCurr').textContent = money(curr);
  $('mLow').textContent = money(low);
  $('mHigh').textContent = money(high);
  $('mAvg').textContent = money(avg);
  const vsEl = $('mVs');
  vsEl.textContent = (vs>=0?'−':'+') + Math.abs(vs).toFixed(1) + '%';
  vsEl.style.color = vs>=0 ? 'var(--up)' : 'var(--down)';
  $('mDisc').textContent = maxDisc>0 ? '−'+Math.round(maxDisc)+'%' : '—';
  $('mUnitLbl').textContent = (p.unit&&p.unit_value) ? `${moneyShort(curr/p.unit_value)} / ${p.unit}` : '';

  const alertBar = $('alertBar');
  if(curr<=low){
    $('alertMsg').textContent = `ALL-TIME LOW! Sitting at its lowest recorded price (${money(curr)}).`;
    alertBar.classList.add('show'); alertBar.classList.remove('deal');
  } else if(vs>0){
    $('alertMsg').textContent = `${vs.toFixed(1)}% below its average of ${money(avg)} — a good deal right now.`;
    alertBar.classList.add('show'); alertBar.classList.add('deal');
  } else {
    alertBar.classList.remove('show'); alertBar.classList.remove('deal');
  }
}

function setRange(r){ chartRange = r; document.querySelectorAll('#rangeSeg button').forEach(b=>b.classList.toggle('active', b.dataset.r===r)); renderSteam(); }
function setMetric(m){ chartMetric = m; document.querySelectorAll('#metricSeg button').forEach(b=>b.classList.toggle('active', b.dataset.m===m)); renderSteam(); }

function filterRange(){
  if(chartRange==='all') return curHistory;
  const days = {'7d':7,'30d':30,'90d':90}[chartRange];
  const cutoff = Date.now() - days*864e5;
  return curHistory.filter(r=>{
    const d = parseDate(r.scraped_at);
    return d ? d.getTime()>=cutoff : true;
  });
}

function renderSteam(){
  if(chart){ chart.destroy(); chart=null; }
  const data = filterRange();
  if(data.length===0){ $('chartLegend').innerHTML='<span class="cl">No data in range</span>'; return; }
  const ctx = $('priceChart').getContext('2d');
  const labels = data.map(r=>fmtDate(r.scraped_at));
  const unit = curProduct ? curProduct.unit : null;
  const unitVal = curProduct ? curProduct.unit_value : null;
  const allLow = Math.min(...curHistory.map(effOf));
  const allHigh = Math.max(...curHistory.map(effOf));

  let cfg;
  if(chartMetric==='discount'){
    cfg = {
      type:'bar',
      data:{ labels, datasets:[{
        label:'Discount %',
        data:data.map(r=>r.discount||0),
        backgroundColor:'rgba(34,211,238,.55)',
        hoverBackgroundColor:'#22d3ee',
        borderRadius:5, borderSkipped:false
      }]},
      options:{
        responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{display:false},
          tooltip:{ backgroundColor:'rgba(11,11,20,.95)', borderColor:'rgba(255,255,255,.1)', borderWidth:1,
            callbacks:{ label: c => ` −${Math.round(c.parsed.y)}% off` } } },
        scales:{ y:{ beginAtZero:true, grid:{color:'rgba(255,255,255,.04)'}, border:{display:false},
                  ticks:{color:'#8a93a6',font:{family:'JetBrains Mono',size:10}, callback:v=>v+'%'} },
                 x:{ grid:{display:false}, border:{display:false}, ticks:{color:'#8a93a6',font:{family:'JetBrains Mono',size:10},maxRotation:0} } }
      }
    };
    $('chartLegend').innerHTML = `<span class="cl"><span class="sw" style="background:#22d3ee"></span> Discount % per snapshot</span>`;
  } else {
    const prices = data.map(effOf);
    const low = Math.min(...prices);
    const lowIdx = prices.indexOf(low);
    const grad = ctx.createLinearGradient(0,0,0,240);
    grad.addColorStop(0,'rgba(139,92,246,.5)'); grad.addColorStop(1,'rgba(139,92,246,0)');
    cfg = {
      type:'line',
      data:{ labels, datasets:[
        { label:'Price', data:prices, borderColor:'#8b5cf6', backgroundColor:grad, fill:true, tension:.35, borderWidth:2.5,
          pointBackgroundColor:prices.map((_,i)=>i===lowIdx?'#fbbf24':'#22d3ee'),
          pointBorderColor:prices.map(()=>'#fff'), pointBorderWidth:1.4,
          pointRadius:prices.map((_,i)=>i===lowIdx?6:3.5), pointHoverRadius:7 },
        { label:'All-time low', data:labels.map(()=>allLow), borderColor:'rgba(251,191,36,.65)', borderDash:[6,5], borderWidth:1.4, pointRadius:0, fill:false }
      ]},
      options:{
        responsive:true, maintainAspectRatio:false,
        interaction:{mode:'index',intersect:false},
        plugins:{ legend:{display:false},
          tooltip:{ backgroundColor:'rgba(11,11,20,.95)', borderColor:'rgba(255,255,255,.1)', borderWidth:1,
            titleFont:{family:'Inter',size:11}, bodyFont:{family:'JetBrains Mono',size:12,weight:'bold'}, padding:10,
            callbacks:{
              label(c){
                if(c.datasetIndex===1) return 'All-time low';
                let s = ' ' + money(c.parsed.y);
                if(unit&&unitVal) s += `  (${moneyShort(c.parsed.y/unitVal)}/${unit})`;
                return s;
              }
            } } },
        scales:{ y:{ suggestedMin:allLow*0.9, grid:{color:'rgba(255,255,255,.04)'}, border:{display:false},
                  ticks:{color:'#8a93a6',font:{family:'JetBrains Mono',size:10}, callback:v=>moneyShort(v)} },
                 x:{ grid:{display:false}, border:{display:false}, ticks:{color:'#8a93a6',font:{family:'JetBrains Mono',size:10},maxRotation:0} } }
      }
    };
    $('chartLegend').innerHTML =
      `<span class="cl"><span class="sw" style="background:#8b5cf6"></span> Price</span>
       <span class="cl"><span class="sw" style="background:#fbbf24"></span> All-time low ${money(allLow)}</span>
       <span class="cl"><span class="dot" style="background:#fbbf24"></span> Lowest point</span>
       <span class="cl">range ৳${moneyShort(allLow)} – ৳${moneyShort(allHigh)}</span>`;
  }
  chart = new Chart(ctx, cfg);
}

// ── PRICE ALERTS (modal) ───────────────────────────────────────────────────────
function renderAlertUi(){
  const id = String(curProduct.id);
  const t = alerts[id];
  const status = $('alertStatus');
  if(t){
    const now = effOf(curProduct);
    const hit = now<=t;
    $('alertTarget').value = t;
    status.innerHTML = hit
      ? `<span class="hit">🔔 TARGET HIT — now ${money(now)} ≤ ${money(t)}</span>`
      : `<span class="set">alert set · will fire at ${money(t)}</span>`;
  } else {
    $('alertTarget').value = '';
    status.innerHTML = '<span class="off">no alert · enter a target price and set</span>';
  }
}

function setAlert(){
  const t = parseFloat($('alertTarget').value);
  if(!t || t<=0){ $('alertTarget').focus(); return; }
  alerts[String(curProduct.id)] = t;
  localStorage.setItem('pb_alerts', JSON.stringify(alerts));
  renderAlertUi();
}

function clearAlert(){
  delete alerts[String(curProduct.id)];
  localStorage.setItem('pb_alerts', JSON.stringify(alerts));
  renderAlertUi();
}

function closeModal(){
  $('overlay').classList.remove('show');
  curHistory = [];
}

// ── UTILS ──────────────────────────────────────────────────────────────────────
function debounce(){
  clearTimeout(window.__st);
  window.__st = setTimeout(()=>{ state.search = $('searchBox').value; loadProducts(1); }, 350);
}
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeModal(); });
document.addEventListener('keydown', e=>{ if((e.key==='/' || e.key==='k') && document.activeElement.tagName!=='INPUT'){ e.preventDefault(); $('searchBox').focus(); } });

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
    r = q1("""
        SELECT (SELECT COUNT(*) FROM products)                 AS total_products,
               (SELECT COUNT(*) FROM categories)              AS total_cats,
               (SELECT COUNT(*) FROM price_history)           AS total_records,
               (SELECT MAX(scraped_at) FROM price_history)    AS last_scraped,
               (SELECT MIN(scraped_at) FROM price_history)    AS first_scraped
    """)
    atl_count = q1(f"""
        SELECT COUNT(*) AS c
        FROM products p
        JOIN ({LATEST_H}) cur ON p.id = cur.product_id
        JOIN ({METRICS_H}) hs  ON p.id = hs.product_id
        WHERE cur.eff <= hs.hist_min
    """).get('c', 0)
    days = 0
    if r.get('first_scraped') and r.get('last_scraped'):
        try:
            f = datetime.fromisoformat(str(r['first_scraped']).replace(' ', 'T'))
            l = datetime.fromisoformat(str(r['last_scraped']).replace(' ', 'T'))
            days = max(1, (l - f).days + 1)
        except Exception:
            days = 0
    return jsonify(total_products=r['total_products'], total_cats=r['total_cats'],
                   total_records=r['total_records'], atl_count=atl_count,
                   last_scraped=r['last_scraped'], first_scraped=r['first_scraped'],
                   days_span=days)

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
    sale    = request.args.get('sale', '0') == '1'
    stock   = request.args.get('stock', '0') == '1'
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
    if sale:
        where.append("cur.discount > 0")
    if stock:
        where.append("cur.stock_available = 1")
    if atl:
        where.append("cur.eff <= hs.hist_min")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order = {
        'price_asc':  "ORDER BY h.eff ASC",
        'price_desc': "ORDER BY h.eff DESC",
        'discount':   "ORDER BY h.discount DESC",
        'drop':       "ORDER BY drop_pct DESC",
    }.get(sort, "ORDER BY p.rowid DESC")

    base_sql = f"""
        FROM products p
        JOIN ({LATEST_H}) cur ON p.id = cur.product_id
        LEFT JOIN ({METRICS_H}) hs ON p.id = hs.product_id
        {where_sql}
    """
    select_sql = f"""
        SELECT p.*, cur.price, cur.special_price, cur.discount, cur.stock_available, cur.eff,
               hs.hist_min, hs.hist_max, hs.hist_avg,
               (cur.eff <= hs.hist_min) AS is_atl,
               ROUND((hs.hist_max - cur.eff)*100.0 / hs.hist_max, 1) AS drop_pct
    """
    total = q1(f"SELECT COUNT(*) AS c {base_sql}", params).get('c', 0)
    rows  = q(f"{select_sql} {base_sql} {order} LIMIT {per} OFFSET {offset}", params)
    return jsonify(products=rows, total=total, page=page)

@app.route('/api/product/<pid>')
def product_detail(pid):
    p = q1(f"""
        SELECT p.*, cur.price, cur.special_price, cur.discount, cur.stock_available, cur.eff,
               hs.hist_min, hs.hist_max, hs.hist_avg,
               (cur.eff <= hs.hist_min) AS is_atl,
               ROUND((hs.hist_max - cur.eff)*100.0 / hs.hist_max, 1) AS drop_pct
        FROM products p
        JOIN ({LATEST_H}) cur ON p.id = cur.product_id
        LEFT JOIN ({METRICS_H}) hs ON p.id = hs.product_id
        WHERE p.id = ?
    """, (pid,))
    return jsonify(p)

@app.route('/api/product/<pid>/history')
def product_history(pid):
    rows = q("""
        SELECT price, special_price, discount, stock_available, scraped_at
        FROM price_history WHERE product_id=? ORDER BY scraped_at
    """, (pid,))
    return jsonify(history=rows)

@app.route('/api/analytics')
def analytics():
    s = q1("""
        SELECT (SELECT COUNT(*) FROM products) AS total_products,
               (SELECT COUNT(*) FROM categories) AS total_cats,
               (SELECT COUNT(*) FROM price_history) AS total_records
    """)
    span = q1("SELECT MIN(scraped_at) AS first_scraped, MAX(scraped_at) AS last_scraped FROM price_history")
    s.update(span)
    s.update(q1(f"""
        SELECT COUNT(*) AS atl_count
        FROM products p
        JOIN ({LATEST_H}) cur ON p.id = cur.product_id
        JOIN ({METRICS_H}) hs ON p.id = hs.product_id
        WHERE cur.eff <= hs.hist_min
    """))
    s.update(q1(f"""
        SELECT ROUND(AVG(discount),1) AS avg_discount,
               ROUND(AVG(COALESCE(NULLIF(special_price,0),price))) AS avg_price
        FROM price_history WHERE id IN (SELECT MAX(id) FROM price_history GROUP BY product_id)
    """))
    days = 0
    if s.get('first_scraped') and s.get('last_scraped'):
        try:
            f = datetime.fromisoformat(str(s['first_scraped']).replace(' ', 'T'))
            l = datetime.fromisoformat(str(s['last_scraped']).replace(' ', 'T'))
            days = max(1, (l - f).days + 1)
        except Exception:
            days = 0
    s['days_span'] = days

    top_drops = q(f"""
        SELECT p.id, p.name, p.product_img, p.category_name, p.sku,
               cur.price, cur.special_price, cur.discount, cur.stock_available, cur.eff,
               ROUND(hs.hist_max,0) AS hist_max, ROUND(hs.hist_avg,0) AS hist_avg,
               ROUND((hs.hist_max - cur.eff)*100.0 / hs.hist_max, 1) AS drop_pct
        FROM products p
        JOIN ({LATEST_H}) cur ON p.id = cur.product_id
        JOIN ({METRICS_H}) hs ON p.id = hs.product_id
        WHERE hs.hist_max > 0 AND cur.stock_available = 1
        ORDER BY drop_pct DESC LIMIT 20
    """)

    top_discounts = q(f"""
        SELECT p.id, p.name, p.product_img, p.category_name, p.sku,
               cur.price, cur.special_price, cur.discount, cur.eff
        FROM products p
        JOIN ({LATEST_H}) cur ON p.id = cur.product_id
        WHERE cur.discount > 0 AND cur.stock_available = 1
        ORDER BY cur.discount DESC LIMIT 20
    """)

    atl_now = q(f"""
        SELECT p.id, p.name, p.product_img, p.category_name, p.sku,
               cur.price, cur.special_price, cur.discount, cur.stock_available, cur.eff,
               ROUND(hs.hist_avg,0) AS hist_avg,
               ROUND((hs.hist_avg - cur.eff)*100.0 / NULLIF(hs.hist_avg,0), 1) AS pct_below_avg
        FROM products p
        JOIN ({LATEST_H}) cur ON p.id = cur.product_id
        JOIN ({METRICS_H}) hs ON p.id = hs.product_id
        WHERE cur.eff <= hs.hist_min AND cur.stock_available = 1
        ORDER BY pct_below_avg DESC LIMIT 20
    """)

    category_dist = q(f"""
        SELECT c.name, COUNT(p.id) AS cnt, ROUND(AVG(cur.discount),1) AS avg_discount
        FROM categories c
        JOIN products p ON p.category_id = c.id
        JOIN ({LATEST_H}) cur ON p.id = cur.product_id
        GROUP BY c.id, c.name
        ORDER BY cnt DESC LIMIT 15
    """)

    return jsonify(summary=s, top_drops=top_drops,
                   top_discounts=top_discounts, atl_now=atl_now,
                   category_dist=category_dist)

if __name__ == '__main__':
    if not os.path.exists(DB_FILE):
        print("⚠ Database not found. Run: python scraper.py first.")
    app.run(debug=True, port=5000)