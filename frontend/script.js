(function () {
  'use strict';

  var DATA = window.sharedeal_data || null;
  var chart = null;

  var todayEff = function (h) {
    if (h.offer != null && h.offer <= h.price) return h.offer;
    return h.price;
  };
  var fmt = function (v) {
    if (v == null) return '—';
    return '৳' + Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 });
  };

  function load() {
    if (DATA) { render(); return; }
    fetch('sharedeal_products.json')
      .then(function (r) { return r.json(); })
      .then(function (d) { DATA = d; render(); })
      .catch(function () {
        document.getElementById('empty').hidden = false;
        document.getElementById('empty').textContent = 'No data found (run run.bat → scrape live first).';
      });
  }

  function derive() {
    var prods = Object.keys(DATA.products).map(function (k) { return DATA.products[k]; });
    var today = DATA.captured_at;
    prods.forEach(function (p) {
      var hist = (p.history || []).slice().sort(function (a, b) { return a.date.localeCompare(b.date); });
      p.hist = hist;
      p.cur = null;
      for (var i = hist.length - 1; i >= 0; i--) { if (hist[i].date <= today) { p.cur = hist[i]; break; } }
      p.prev = null;
      for (var i2 = hist.length - 2; i2 >= 0; i2--) { if (hist[i2].date < (p.cur ? p.cur.date : today)) { p.prev = hist[i2]; break; } }
      var effs = hist.map(todayEff).filter(function (v) { return v != null; });
      p.low = effs.length ? Math.min.apply(null, effs) : null;
      p.high = hist.map(function (h) { return h.price; }).filter(function (v) { return v != null; }).length
        ? Math.max.apply(null, hist.map(function (h) { return h.price; }).filter(function (v) { return v != null; }))
        : null;
      p.eff = p.cur ? todayEff(p.cur) : null;
      p.prevEff = p.prev ? todayEff(p.prev) : null;
      p.chg = (p.eff != null && p.prevEff != null) ? p.eff - p.prevEff : null;
      p.disc = (p.cur && p.cur.offer != null && p.cur.price) ? Math.round((1 - p.cur.offer / p.cur.price) * 100) : 0;
      p.series = effs;
    });
    return prods;
  }

  var all = [];
  var state = { search: '', cat: 'all', sort: 'name' };

  function render() {
    var prods = derive();
    all = prods;
    var cats = DATA.categories || [];
    document.getElementById('st-products').textContent = prods.length;
    document.getElementById('st-cats').textContent = cats.length;
    var days = {};
    prods.forEach(function (p) { p.hist.forEach(function (h) { days[h.date] = 1; }); });
    document.getElementById('st-days').textContent = Object.keys(days).length;
    document.getElementById('st-on-sale').textContent = prods.filter(function (p) { return p.cur && p.cur.offer != null && p.cur.offer < p.cur.price; }).length;
    var changed = prods.filter(function (p) { return p.chg != null && Math.abs(p.chg) > 0.001; }).length;
    document.getElementById('st-changed').textContent = changed;
    document.getElementById('last-updated').textContent = 'as of ' + (DATA.captured_at || '—') + ' · ' + (DATA.store || 'ShareDeal');

    var sel = document.getElementById('cat-filter');
    sel.innerHTML = '<option value="all">All categories</option>' + cats.map(function (c) {
      return '<option value="' + c.id + '">' + c.name + '</option>';
    }).join('');

    renderGrid();
  }

  function matches(p) {
    if (state.search && p.name.toLowerCase().indexOf(state.search) < 0 && (p.sku || '').toLowerCase().indexOf(state.search) < 0) return false;
    if (state.cat !== 'all' && String(p.category_id) !== String(state.cat)) return false;
    return true;
  }

  function sortRows(list) {
    var s = state.sort;
    var copy = list.slice();
    copy.sort(function (a, b) {
      if (s === 'price') return (a.eff == null ? Infinity : a.eff) - (b.eff == null ? Infinity : b.eff);
      if (s === 'drop') return (b.chg == null ? 0 : b.chg) - (a.chg == null ? 0 : a.chg);
      if (s === 'rise') return (a.chg == null ? 0 : a.chg) - (b.chg == null ? 0 : b.chg);
      if (s === 'sale') return (b.disc || 0) - (a.disc || 0);
      return a.name.localeCompare(b.name, 'en');
    });
    return copy;
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function renderGrid() {
    var rows = sortRows(all.filter(matches));
    var grid = document.getElementById('grid');
    var html = rows.map(function (p, i) {
      var onSale = p.cur && p.cur.offer != null && p.cur.offer < p.cur.price;
      var regular = p.cur ? fmt(p.cur.price) : '—';
      var priceHtml = onSale
        ? '<span class="strike">' + regular + '</span> <span class="sale">' + fmt(p.eff) + '</span>'
        : '<span class="price-main">' + fmt(p.eff) + '</span>';
      if (p.cur && p.cur.group != null) priceHtml += ' <span class="chip group-chip" title="Group buy">' + fmt(p.cur.group) + '</span>';
      if (p.disc > 0) priceHtml += ' <span class="chip sale-chip">-' + p.disc + '%</span>';
      var chg = '';
      if (p.chg != null && p.chg !== 0) {
        var cls = p.chg < 0 ? 'down' : 'up';
        chg = '<span class="' + cls + '">' + (p.chg < 0 ? '▼' : '▲') + ' ' + fmt(Math.abs(p.chg)) + '</span>';
      } else {
        chg = '<span class="flat">—</span>';
      }
      var img = p.image
        ? '<img src="' + p.image + '" loading="lazy" alt="" onerror="this.parentElement.classList.add(\'noimg\');this.style.display=\'none\'"/>'
        : '<div class="ph">' + escapeHtml((p.name || '?').charAt(0)) + '</div>';
      return '<div class="card' + (onSale ? ' on-sale' : '') + '" data-id="' + p.id + '">'
        + '<div class="c-img">' + img + '</div>'
        + '<div class="c-body">'
        + '<div class="c-name" title="' + escapeHtml(p.name) + '">' + escapeHtml(p.name) + '</div>'
        + '<div class="c-cat">' + escapeHtml(p.category || 'Uncategorized') + '</div>'
        + '<div class="c-price">' + priceHtml + '</div>'
        + '<div class="c-chg">' + chg + '</div>'
        + '</div>'
        + '<canvas class="spark" data-id="' + p.id + '" width="220" height="30"></canvas>'
        + '</div>';
    }).join('');
    grid.innerHTML = html;
    document.getElementById('empty').hidden = rows.length > 0;
    document.getElementById('result-count').textContent = rows.length + ' items';

    Array.prototype.forEach.call(grid.querySelectorAll('.card'), function (card) {
      card.addEventListener('click', function () { openDetail(card.getAttribute('data-id')); });
    });
    Array.prototype.forEach.call(grid.querySelectorAll('.spark'), drawSpark);
  }

  function sparkColor(p) {
    if (!p.series || p.series.length < 2) return '#5c6470';
    var a = p.series[0], b = p.series[p.series.length - 1];
    if (b < a) return '#7fbf3a';
    if (b > a) return '#d4502f';
    return '#7aa2f7';
  }

  function drawSpark(canvas) {
    var p = all.find(function (x) { return String(x.id) === String(canvas.getAttribute('data-id')); });
    if (!p) return;
    var ctx = canvas.getContext('2d');
    var W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    var pts = p.series.filter(function (v) { return v != null; });
    if (pts.length < 2) {
      ctx.fillStyle = '#5c6470';
      ctx.font = '10px Inter, sans-serif';
      ctx.fillText('history builds daily', 6, H / 2 + 3);
      return;
    }
    var min = Math.min.apply(null, pts), max = Math.max.apply(null, pts);
    var span = (max - min) || 1;
    var pad = 3;
    var x = function (i) { return pad + (i / (pts.length - 1)) * (W - 2 * pad); };
    var y = function (v) { return H - pad - ((v - min) / span) * (H - 2 * pad); };
    var color = sparkColor(p);
    ctx.beginPath();
    ctx.moveTo(x(0), H);
    ctx.lineTo(x(0), y(pts[0]));
    pts.forEach(function (v, i) { ctx.lineTo(x(i), y(v)); });
    ctx.lineTo(x(pts.length - 1), H);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.12;
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.beginPath();
    pts.forEach(function (v, i) { i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(0), y(v)); });
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x(pts.length - 1), y(pts[pts.length - 1]), 2.4, 0, Math.PI * 2);
    ctx.fill();
  }

  function openDetail(id) {
    var p = all.find(function (x) { return String(x.id) === String(id); });
    if (!p) return;
    document.getElementById('d-name').textContent = p.name;
    document.getElementById('d-sku').textContent = p.sku ? ('SKU: ' + p.sku) : '';
    document.getElementById('d-cat').textContent = p.category || '';
    document.getElementById('d-unit').textContent = [p.volume, p.unit].filter(Boolean).join(' ');
    var img = document.getElementById('d-img');
    if (p.image) { img.src = p.image; img.style.display = ''; } else { img.style.display = 'none'; }
    document.getElementById('d-now').textContent = fmt(p.eff);
    document.getElementById('d-regular').textContent = fmt(p.cur ? p.cur.price : null);
    document.getElementById('d-offer').textContent = fmt(p.cur ? p.cur.offer : null);
    document.getElementById('d-group').textContent = fmt(p.cur ? p.cur.group : null);
    document.getElementById('d-low').textContent = fmt(p.low);
    document.getElementById('d-high').textContent = fmt(p.high);
    var dropEl = document.getElementById('d-drop');
    if (p.chg != null && p.chg !== 0) {
      dropEl.textContent = (p.chg > 0 ? '+' : '') + fmt(p.chg);
      dropEl.className = p.chg < 0 ? 'down' : 'up';
    } else {
      dropEl.textContent = '—';
      dropEl.className = 'n';
    }
    var hist = p.hist;
    document.getElementById('d-hist').querySelector('tbody').innerHTML = hist.map(function (h) {
      return '<tr><td>' + h.date + '</td><td>' + fmt(h.price) + '</td><td>' + fmt(h.offer) + '</td><td>' + fmt(h.group) + '</td><td>' + (h.stock != null ? h.stock : '—') + '</td></tr>';
    }).join('');
    drawChart(hist);
    document.getElementById('drawer').classList.add('open');
    document.getElementById('scrim').classList.add('show');
  }

  function drawChart(hist) {
    var canvas = document.getElementById('d-chart');
    if (typeof Chart === 'undefined') {
      canvas.parentElement.innerHTML = '<div class="empty">Chart.js not available (offline?).</div>';
      return;
    }
    var labels = hist.map(function (h) { return h.date; });
    var datasets = [
      { label: 'Regular', data: hist.map(function (h) { return h.price; }), borderColor: '#7aa2f7', backgroundColor: 'rgba(122,162,247,0.08)', pointRadius: 3, borderWidth: 1.6, spanGaps: true },
      { label: 'Offer', data: hist.map(function (h) { return h.offer; }), borderColor: '#7fbf3a', backgroundColor: 'rgba(127,191,58,0.16)', pointRadius: 3, borderWidth: 2, fill: true, spanGaps: true },
      { label: 'Group', data: hist.map(function (h) { return h.group; }), borderColor: '#e2c07c', borderDash: [5, 3], pointRadius: 3, borderWidth: 1.6, fill: false, spanGaps: true }
    ];
    if (chart) chart.destroy();
    chart = new Chart(canvas, {
      type: 'line',
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#151515',
            borderColor: '#2b2b2b',
            borderWidth: 1,
            titleColor: '#9aa4b2',
            bodyColor: '#e8e8e8',
            callbacks: {
              label: function (ctx) {
                return ctx.dataset.label + ': ৳' + (ctx.parsed.y == null ? '—' : Number(ctx.parsed.y).toLocaleString('en-IN'));
              }
            }
          }
        },
        scales: {
          x: { ticks: { color: '#9aa4b2', maxRotation: 0 }, grid: { color: 'rgba(255,255,255,0.04)' } },
          y: { ticks: { color: '#9aa4b2', callback: function (v) { return '৳' + v; } }, grid: { color: 'rgba(255,255,255,0.05)' } }
        }
      }
    });
  }

  function closeDetail() {
    document.getElementById('drawer').classList.remove('open');
    document.getElementById('scrim').classList.remove('show');
  }

  function bindUI() {
    document.getElementById('search').addEventListener('input', function (e) { state.search = e.target.value.toLowerCase().trim(); renderGrid(); });
    document.getElementById('cat-filter').addEventListener('change', function (e) { state.cat = e.target.value; renderGrid(); });
    document.getElementById('sort').addEventListener('change', function (e) { state.sort = e.target.value; renderGrid(); });
    document.getElementById('d-close').addEventListener('click', closeDetail);
    document.getElementById('scrim').addEventListener('click', closeDetail);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDetail(); });
  }

  bindUI();
  load();
})();