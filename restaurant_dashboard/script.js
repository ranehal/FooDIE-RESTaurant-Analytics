'use strict';

const IMG_BASE = 'https://cdn.foodibd.com';
const STORE = {
  favorites: 'foodie_brutal_favorites_v1', cart: 'foodie_brutal_cart_v1',
  compare: 'foodie_brutal_compare_v1', watch: 'foodie_brutal_watch_v1',
  theme: 'foodie_brutal_theme_v1', grid: 'foodie_brutal_grid_v1'
};
const BATCH = 36;

function storageGet(key) { try { return localStorage.getItem(key); } catch { return null; } }
function storageSet(key, value) { try { localStorage.setItem(key, value); } catch {} }

const state = {
  data: null, locations: [], restaurants: [], dishes: [], restaurantMap: new Map(), dishMap: new Map(),
  restsByLoc: [], dishesByLoc: [], dishesByRest: new Map(), cuisines: [],
  location: 0, view: 'restaurants', query: '', cuisine: '', minRating: 0, maxFee: 999,
  maxDistance: 999, sort: 'distance', filters: new Set(), priceFilters: new Set(),
  customChange: 12, newDays: 7, newFrom: '', newTo: '', meanFrom: '', meanTo: '', meanVersion: 0,
  renderLimit: BATCH, filtered: [], grid: Number(storageGet(STORE.grid) || 4), loadAll: storageGet('fe_load_all')==='1',
  favorites: new Set(readJSON(STORE.favorites, [])), cart: readJSON(STORE.cart, {}),
  compare: readJSON(STORE.compare, { type: '', ids: [] }), watch: readJSON(STORE.watch, {}),
  analyticsDirty: true, viewerKey: '', viewerKeys: [], viewerIndex: -1, viewerPointerX: null
};

const $ = (id) => document.getElementById(id);
const qsa = (sel, root = document) => [...root.querySelectorAll(sel)];
const money = (v) => `৳${Number(v || 0).toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
const pct = (v) => `${Math.round(Number(v || 0))}%`;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const esc = (v = '') => String(v).replace(/[&<>'"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const num = (v) => Number.isFinite(Number(v)) ? Number(v) : 0;

function readJSON(key, fallback) {
  try { const value = JSON.parse(storageGet(key)); return value ?? fallback; }
  catch { return fallback; }
}
function writeJSON(key, value) { storageSet(key, JSON.stringify(value)); }
function setLoading(text, value) {
  $('loaderText').textContent = text; $('loaderPct').textContent = `${value}%`; $('loaderFill').style.width = `${value}%`;
}
function debounce(fn, wait = 120) { let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); }; }
function imageUrl(path) { if (!path) return ''; if (/^https?:/i.test(path)) return path; return `${IMG_BASE}${path.startsWith('/') ? '' : '/'}${path}`; }
function bestRestaurantImage(r) {
  return imageUrl(r.branchImages?.['5']?.coverImage || r.coverImage || r.image || '');
}
function dateLabel(value) {
  if (!value) return 'UNKNOWN';
  const d = new Date(value); return Number.isNaN(d.getTime()) ? 'UNKNOWN' : d.toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' }).toUpperCase();
}

function parseDateValue(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}
function mediaDate(...values) {
  for (const value of values) {
    const text = String(value || '');
    const match = text.match(/(20\d{12}|20\d{6})/);
    if (!match) continue;
    const raw = match[1];
    const y = Number(raw.slice(0,4)), mo = Number(raw.slice(4,6))-1, day = Number(raw.slice(6,8));
    const h = raw.length >= 10 ? Number(raw.slice(8,10)) : 12;
    const mi = raw.length >= 12 ? Number(raw.slice(10,12)) : 0;
    const sec = raw.length >= 14 ? Number(raw.slice(12,14)) : 0;
    const d = new Date(Date.UTC(y, mo, day, h, mi, sec));
    if (!Number.isNaN(d.getTime()) && d.getUTCFullYear() === y && d.getUTCMonth() === mo && d.getUTCDate() === day) return d;
  }
  return null;
}
function normalizeHistorySource(raw) {
  if (!raw) return [];
  const rows = [];
  if (Array.isArray(raw)) rows.push(...raw);
  else if (typeof raw === 'object') {
    for (const [date, value] of Object.entries(raw)) {
      if (value && typeof value === 'object') rows.push({ date, ...value });
      else rows.push({ date, price: value });
    }
  }
  const points = [];
  for (const row of rows) {
    if (row == null) continue;
    const date = parseDateValue(row.date ?? row.timestamp ?? row.recordedAt ?? row.createdAt ?? row.time ?? row.day);
    const price = num(row.price ?? row.value ?? row.currentPrice ?? row.actualPrice ?? row.amount);
    if (date && price > 0) points.push({ date: date.toISOString(), price });
  }
  points.sort((a,b)=>new Date(a.date)-new Date(b.date));
  return points.filter((point,index,array)=>index===0 || point.date!==array[index-1].date || point.price!==array[index-1].price);
}
function extractDishHistory(menu, currentPrice) {
  const source = menu.priceHistory ?? menu.price_history ?? menu.history ?? menu.histories ?? menu.historyPoints ?? menu.priceRecords ?? null;
  const historical = normalizeHistorySource(source);
  const scraped = parseDateValue(state.data?.scrapedAt);
  const points = [...historical];
  if (scraped && currentPrice > 0) {
    const stamp = scraped.toISOString();
    const last = points[points.length - 1];
    if (!last || last.date !== stamp || last.price !== currentPrice) points.push({ date: stamp, price: currentPrice, current: true });
  }
  points.sort((a,b)=>new Date(a.date)-new Date(b.date));
  return { points, hasSeries: historical.length > 0, source: historical.length ? 'DATED HISTORY + CURRENT SNAPSHOT' : 'CURRENT SNAPSHOT ONLY' };
}
function extractFirstSeen(menu) {
  return parseDateValue(menu.firstSeen ?? menu.first_seen ?? menu.discoveredAt ?? menu.createdAt ?? menu.created_at) || mediaDate(menu.image, menu.bannerImage);
}
function dateInRange(date, from, to) {
  if (!date) return false;
  const time = new Date(date).getTime();
  const start = from ? new Date(`${from}T00:00:00`).getTime() : -Infinity;
  const end = to ? new Date(`${to}T23:59:59.999`).getTime() : Infinity;
  return time >= start && time <= end;
}
function priceMetrics(d) {
  const cacheKey = `${state.meanVersion}|${state.meanFrom}|${state.meanTo}`;
  if (d._metricsKey === cacheKey && d._metrics) return d._metrics;
  const full = Array.isArray(d.history) ? d.history : [];
  const ranged = full.filter(point => dateInRange(point.date, state.meanFrom, state.meanTo));
  const analysis = (state.meanFrom || state.meanTo) ? ranged : full;
  const mean = analysis.length >= 2 ? analysis.reduce((sum,p)=>sum+p.price,0)/analysis.length : null;
  const previousPoint = full.length >= 2 ? full[full.length-2] : null;
  const previous = previousPoint?.price || (d.oldPrice > 0 ? d.oldPrice : null);
  const change = previous ? d.price - previous : 0;
  const changePct = previous ? change / previous * 100 : 0;
  const baseline = mean || (d.oldPrice > 0 ? d.oldPrice : null);
  const dealPct = baseline && baseline > d.price ? (baseline-d.price)/baseline*100 : 0;
  const fullMin = full.length ? Math.min(...full.map(p=>p.price)) : d.price;
  const allTimeLow = d.hasHistory && full.length >= 2 && d.price <= fullMin + 0.0001;
  const result = { mean, previous, change, changePct, baseline, dealPct, fullMin, allTimeLow, wait: Boolean(baseline && d.price > baseline) };
  d._metricsKey = cacheKey; d._metrics = result; return result;
}
function itemAgeDays(d) {
  if (!d.firstSeen) return Infinity;
  const reference = parseDateValue(state.data?.scrapedAt) || new Date();
  return Math.floor((reference.getTime() - new Date(d.firstSeen).getTime()) / 86400000);
}

window.addEventListener('DOMContentLoaded', init);
async function init() {
  setLoading('FETCHING 14 MB CATALOGUE', 12);
  try {
    const res = await fetch('data.json');
    if (!res.ok) throw new Error(`DATA ${res.status}`);
    state.data = await res.json();
    setLoading('INDEXING RESTAURANTS + DISHES', 45);
    processData();
    setLoading('BUILDING BRUTAL INTERFACE', 74);
    setupUI();
    renderAll();
    checkWatchTargets();
    setLoading('READY TO EAT', 100);
    setTimeout(() => $('loader').classList.add('hide'), 120);
  } catch (error) {
    console.error(error);
    setLoading(`FAILED: ${error.message}`, 0);
    $('loader').style.background = '#ff304c';
  }
}

function processData() {
  const locations = Array.isArray(state.data.locations) ? state.data.locations : [];
  state.locations = locations;
  state.restsByLoc = locations.map(() => []);
  state.dishesByLoc = locations.map(() => []);
  const cuisineSet = new Set();

  locations.forEach((loc, locIndex) => {
    (loc.restaurants || []).forEach((raw) => {
      const key = `r:${locIndex}:${raw.id}`;
      const categoryForMenu = new Map();
      (raw.categories || []).forEach((cat) => {
        (cat.menuIds || []).forEach((id) => categoryForMenu.set(String(id), cat.name || 'Uncategorized'));
      });
      const rawMenus = Object.values(raw.menus || {});
      let discountedCount = 0, totalDiscount = 0, maxDiscount = 0, popularDishes = 0;
      let variationCount = 0, addonCount = 0, photoCount = 0, descriptionCount = 0;
      const restaurantDishKeys = [];

      rawMenus.forEach((m) => {
        const price = num(m.price), oldPrice = num(m.oldPrice);
        const discountPct = oldPrice > price && price > 0 ? ((oldPrice - price) / oldPrice) * 100 : 0;
        const saving = oldPrice > price ? oldPrice - price : 0;
        const variationIds = Array.isArray(m.variationIds) ? m.variationIds : [];
        const addonIds = Array.isArray(m.addOnCategoryIds) ? m.addOnCategoryIds : [];
        const hasVariation = Boolean(num(m.hasVariation) || variationIds.length || Object.keys(m.variationOtherInfo || {}).length);
        const hasAddons = addonIds.length > 0 || Object.values(m.variationOtherInfo || {}).some((v) => (v.addOnCategoryIds || []).length);
        if (discountPct > 0) { discountedCount++; totalDiscount += discountPct; maxDiscount = Math.max(maxDiscount, discountPct); }
        if (m.isPopular) popularDishes++;
        if (hasVariation) variationCount++;
        if (hasAddons) addonCount++;
        if (m.image || m.bannerImage) photoCount++;
        if (m.description) descriptionCount++;
        const dishKey = `d:${locIndex}:${raw.id}:${m.id}`;
        const category = categoryForMenu.get(String(m.id)) || 'Uncategorized';
        const historyInfo = extractDishHistory(m, price);
        const firstSeenDate = extractFirstSeen(m);
        const dish = {
          key: dishKey, id: m.id, restKey: key, locIndex, name: String(m.name || 'Unnamed dish').trim(),
          price, oldPrice, discountPct, saving, image: imageUrl(m.image || ''), banner: imageUrl(m.bannerImage || m.image || ''),
          description: m.description || '', isPopular: Boolean(m.isPopular), category,
          variationIds, variationInfo: m.variationOtherInfo || {}, addonIds, hasVariation, hasAddons,
          history: historyInfo.points, hasHistory: historyInfo.hasSeries, historySource: historyInfo.source,
          firstSeen: firstSeenDate ? firstSeenDate.toISOString() : null,
          restaurantName: raw.name || 'Unknown restaurant', primaryCuisine: raw.primaryCuisine || 'Other',
          restaurantRating: num(raw.rating), distance: num(raw.distance), deliveryCharge: num(raw.deliveryCharge),
          deliveryTime: num(raw.totalDeliveryTime || raw.deliveryTime), landedPrice: price + num(raw.deliveryCharge),
          search: `${m.name || ''} ${category} ${raw.name || ''} ${raw.primaryCuisine || ''} ${(raw.cuisineList || []).join(' ')}`.toLowerCase()
        };
        state.dishes.push(dish); state.dishMap.set(dishKey, dish); state.dishesByLoc[locIndex].push(dishKey); restaurantDishKeys.push(dishKey);
      });

      const cuisines = [...new Set([raw.primaryCuisine, ...(raw.cuisineList || [])].filter(Boolean))];
      cuisines.forEach((c) => cuisineSet.add(c));
      const menuCount = rawMenus.length;
      const photoCoverage = menuCount ? photoCount / menuCount : 0;
      const avgDiscount = discountedCount ? totalDiscount / discountedCount : 0;
      const dealDensity = menuCount ? discountedCount / menuCount : 0;
      const rating = num(raw.rating), ratingConfidence = Math.min(1, Math.log10(num(raw.ratingCount) + 1) / 3);
      const valueScore = clamp(
        (rating / 5) * 32 + ratingConfidence * 10 + clamp(avgDiscount / 30, 0, 1) * 23 +
        clamp((25 - num(raw.deliveryTime)) / 15, 0, 1) * 15 + clamp((55 - num(raw.deliveryCharge)) / 20, 0, 1) * 10 + photoCoverage * 10,
        0, 100
      );
      const restaurant = {
        key, id: raw.id, locIndex, locationName: loc.name, name: raw.name || 'Unnamed restaurant', image: imageUrl(raw.image || ''),
        cover: bestRestaurantImage(raw), primaryCuisine: raw.primaryCuisine || 'Other', cuisines, rating, ratingCount: num(raw.ratingCount || raw.totalReviewCount),
        distance: num(raw.distance), deliveryTime: num(raw.totalDeliveryTime || raw.deliveryTime), prepTime: num(raw.preparationTime),
        deliveryCharge: num(raw.deliveryCharge), minOrder: num(raw.minOrderValue), deliveryRadius: num(raw.deliveryRadius), pickupTime: num(raw.pickupTime),
        preorder: Boolean(raw.isTakePreOrder), popular: Boolean(raw.isPopular), workingHours: raw.workingHours || [],
        menuCount, discountedCount, avgDiscount, maxDiscount, dealDensity, popularDishes, variationCount, addonCount,
        photoCount, descriptionCount, photoCoverage, valueScore, dishKeys: restaurantDishKeys,
        search: `${raw.name || ''} ${raw.primaryCuisine || ''} ${cuisines.join(' ')}`.toLowerCase(), raw
      };
      state.restaurants.push(restaurant); state.restaurantMap.set(key, restaurant); state.restsByLoc[locIndex].push(key); state.dishesByRest.set(key, restaurantDishKeys);
    });
  });
  state.cuisines = [...cuisineSet].sort((a,b) => a.localeCompare(b));
}

function setupUI() {
  document.body.dataset.theme = storageGet(STORE.theme) || 'ink';
  $('gridRange').value = clamp(state.grid, 2, 6); $('gridValue').textContent = state.grid;
  $('grid').style.setProperty('--cols', state.grid);
  $('customChangePct').value = state.customChange; $('newDays').value = state.newDays;
  const historyCount = state.dishes.filter(d=>d.hasHistory).length;
  $('historyDataNote').textContent = historyCount ? `${historyCount.toLocaleString()} ITEMS INCLUDE REAL DATED HISTORY. OTHERS USE CURRENT/OLD SNAPSHOTS ONLY.` : 'NO DATED HISTORY EXISTS IN THIS JSON. CURRENT/OLD SNAPSHOTS AND MEDIA DATES ONLY.';
  $('scrapedAt').textContent = dateLabel(state.data.scrapedAt);
  $('tickerTrack').textContent = `FOODIEATS // ${state.restaurants.length.toLocaleString()} RESTAURANTS // ${state.dishes.length.toLocaleString()} DISHES // ${state.locations.map(l => l.name.toUpperCase()).join(' VS ')} // ${state.dishes.filter(d=>d.discountPct>0).length.toLocaleString()} DISCOUNTS // CUSTOMIZATION INTELLIGENCE // OPENING HOURS // LANDED COST // `.repeat(2);

  $('locationTabs').innerHTML = state.locations.map((loc, i) => `<button class="location-tab ${i===0?'active':''}" data-location="${i}"><i class="fa-solid fa-location-dot"></i><br>${esc(loc.name.toUpperCase())}</button>`).join('');
  $('cuisineSelect').innerHTML = `<option value="">ALL</option>${state.cuisines.map(c=>`<option value="${esc(c)}">${esc(c.toUpperCase())}</option>`).join('')}`;
  renderCuisineList(); updateSortOptions(); setupListeners();
}

function setupListeners() {
  $('locationTabs').addEventListener('click', (e) => { const b=e.target.closest('[data-location]'); if(!b)return; setLocation(Number(b.dataset.location)); });
  qsa('.view-tab').forEach((b) => b.addEventListener('click', () => setView(b.dataset.view)));
  $('globalSearch').addEventListener('input', debounce((e) => { state.query=e.target.value.trim().toLowerCase(); state.renderLimit=BATCH; renderGrid(); renderSuggestions(e.target.value); }, 90));
  $('globalSearch').addEventListener('focus', () => renderSuggestions($('globalSearch').value));
  $('clearSearch').addEventListener('click', () => { $('globalSearch').value=''; state.query=''; hideSuggestions(); renderGrid(); });
  document.addEventListener('click', (e) => { if (!e.target.closest('.masthead-center')) hideSuggestions(); });
  $('suggestions').addEventListener('click', (e) => { const b=e.target.closest('[data-suggest]'); if(!b)return; const [type,key]=b.dataset.suggest.split('|'); hideSuggestions(); type==='r'?openRestaurant(key):openDish(key); });
  $('sidebarSearch').addEventListener('input', () => renderCuisineList());
  $('cuisineList').addEventListener('click', (e) => { const b=e.target.closest('[data-cuisine]'); if(!b)return; state.cuisine=b.dataset.cuisine; $('cuisineSelect').value=state.cuisine; state.renderLimit=BATCH; renderCuisineList(); renderGrid(); closeSidebar(); });
  $('cuisineSelect').addEventListener('change', (e) => { state.cuisine=e.target.value; state.renderLimit=BATCH; renderCuisineList(); renderGrid(); });
  $('ratingSelect').addEventListener('change', (e) => { state.minRating=num(e.target.value); state.renderLimit=BATCH; renderGrid(); });
  $('feeSelect').addEventListener('change', (e) => { state.maxFee=num(e.target.value); state.renderLimit=BATCH; renderGrid(); });
  $('distanceSelect').addEventListener('change', (e) => { state.maxDistance=num(e.target.value); state.renderLimit=BATCH; renderGrid(); });
  $('sortSelect').addEventListener('change', (e) => { state.sort=e.target.value; renderGrid(); });
  $('gridRange').addEventListener('input', (e) => { state.grid=num(e.target.value); $('gridValue').textContent=state.grid; $('grid').style.setProperty('--cols',state.grid); writeJSON(STORE.grid,state.grid); });
  $('primaryFilters').addEventListener('click', (e) => { const b=e.target.closest('[data-filter]'); if(!b)return; const f=b.dataset.filter; state.filters.has(f)?state.filters.delete(f):state.filters.add(f); b.classList.toggle('active',state.filters.has(f)); state.renderLimit=BATCH; renderGrid(); });
  $('priceFilterStrip').addEventListener('click', (e) => { const b=e.target.closest('[data-price-filter]'); if(!b)return; togglePriceFilter(b.dataset.priceFilter); });
  $('dishControls').addEventListener('click', (e) => { const b=e.target.closest('[data-price-filter]'); if(!b||b.closest('#priceFilterStrip'))return; togglePriceFilter(b.dataset.priceFilter); });
  $('customChangePct').addEventListener('input', debounce((e)=>{state.customChange=clamp(num(e.target.value)||12,1,95);state.renderLimit=BATCH;renderGrid();},100));
  $('newDays').addEventListener('input', debounce((e)=>{state.newDays=clamp(num(e.target.value)||7,1,3650);state.renderLimit=BATCH;renderGrid();},100));
  ['newFrom','newTo'].forEach(id=>$(id).addEventListener('change',(e)=>{state[id]=e.target.value;state.renderLimit=BATCH;if(state.priceFilters.has('new_range'))renderGrid();}));
  ['meanFrom','meanTo'].forEach(id=>$(id).addEventListener('change',(e)=>{state[id]=e.target.value;state.meanVersion++;state.renderLimit=BATCH;renderGrid();if(state.viewerKey)renderDishViewer();}));
  $('clearMean').addEventListener('click',()=>{state.meanFrom='';state.meanTo='';$('meanFrom').value='';$('meanTo').value='';state.meanVersion++;renderGrid();if(state.viewerKey)renderDishViewer();});
  $('loadMoreBtn').addEventListener('click',()=>{state.renderLimit+=BATCH;renderGrid(false);});
  $('loadAllToggle').addEventListener('click',()=>{state.loadAll=!state.loadAll;storageSet('fe_load_all',state.loadAll?'1':'0');syncLoadAllToggle();renderGrid(false);});
  $('grid').addEventListener('click', handleGridClick);
  $('favoriteVisibleBtn').addEventListener('click', favoriteVisible);
  $('favoritesOnlyBtn').addEventListener('click',()=>{state.filters.has('favorites')?state.filters.delete('favorites'):state.filters.add('favorites');$('favoritesOnlyBtn').classList.toggle('active',state.filters.has('favorites'));renderGrid();});
  $('resetBtn').addEventListener('click', resetFilters);
  $('themeBtn').addEventListener('click', toggleTheme);
  $('surpriseBtn').addEventListener('click', surpriseMe);
  $('cartBtn').addEventListener('click', renderCartDrawer);
  $('watchBtn').addEventListener('click', renderWatchDrawer);
  $('compareBtn').addEventListener('click', renderCompareDrawer);
  $('compareNowBtn').addEventListener('click', renderCompareDrawer);
  $('compareClearBtn').addEventListener('click', clearCompare);
  $('compareTrayItems').addEventListener('click',(e)=>{const b=e.target.closest('[data-remove-compare]');if(b)removeCompare(b.dataset.removeCompare);});
  $('detailModal').addEventListener('click',(e)=>{ if(e.target===$('detailModal')||e.target.closest('[data-close-modal]'))closeModal(); else handleModalAction(e); });
  $('dishViewerClose').addEventListener('click',closeDishViewer);
  $('historyCloseBtn')?.addEventListener('click',closeDishViewer);
  $('dishViewerPrev').addEventListener('click',()=>cycleDish(-1)); $('dishViewerNext').addEventListener('click',()=>cycleDish(1));
  $('dishViewerHeader').addEventListener('click',handleViewerAction);
  $('dishViewerStage').addEventListener('pointerdown',(e)=>{state.viewerPointerX=e.clientX;});
  $('dishViewerStage').addEventListener('pointerup',(e)=>{if(state.viewerPointerX===null)return;const dx=e.clientX-state.viewerPointerX;state.viewerPointerX=null;if(Math.abs(dx)>55)cycleDish(dx<0?1:-1);});
  window.addEventListener('resize',debounce(()=>{if(state.viewerKey)drawPriceHistory();},100));
  $('drawerClose').addEventListener('click', closeDrawer); $('drawerOverlay').addEventListener('click',closeDrawer);
  $('drawerContent').addEventListener('click',handleDrawerClick);
  $('sidebarOpen').addEventListener('click',openSidebar); $('sidebarClose').addEventListener('click',closeSidebar); $('sidebarOverlay').addEventListener('click',closeSidebar);
  document.addEventListener('keydown',(e)=>{
    const isInput = /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
    const isCloseKey = e.key === 'Escape' || (!isInput && (e.key === ' ' || e.code === 'Space'));
    if (isCloseKey && (state.viewerKey || $('detailModal').classList.contains('open') || $('drawer').classList.contains('open') || $('sidebar').classList.contains('open'))) {
      e.preventDefault();
      closeDishViewer();
      closeModal();
      closeDrawer();
      closeSidebar();
      return;
    }
    if (state.viewerKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
      e.preventDefault();
      cycleDish(e.key === 'ArrowRight' ? 1 : -1);
      return;
    }
    if (e.key === '/' && !isInput) {
      e.preventDefault();
      $('globalSearch').focus();
    }
  });
}

function setLocation(index) {
  state.location = clamp(index,0,state.locations.length-1); state.renderLimit=BATCH; state.analyticsDirty=true;
  qsa('[data-location]').forEach((b)=>b.classList.toggle('active',Number(b.dataset.location)===state.location));
  renderCuisineList(); renderAll();
}
function setView(view) {
  state.view=view;state.renderLimit=BATCH;state.sort=view==='dishes'?'price_drop':'distance';
  qsa('.view-tab').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
  $('dishControls').hidden=view!=='dishes'; $('grid').hidden=view==='analytics'; $('loadMoreBtn').hidden=true; $('analytics').hidden=view!=='analytics';
  $('viewTitle').textContent=view==='restaurants'?'RESTAURANT WAR ROOM':view==='dishes'?'DISH DEAL PIT':'MARKET INTELLIGENCE';
  updateSortOptions(); if(view==='analytics')renderAnalytics(); else renderGrid();
}
function updateSortOptions() {
  const options = state.view==='dishes' ? [
    ['price_drop','BIGGEST PRICE DROP'],['price_rise','BIGGEST PRICE RISE'],['price_change','LARGEST PRICE CHANGE'],['newest','NEWEST FIRST'],['price_asc','PRICE LOW → HIGH'],['price_desc','PRICE HIGH → LOW'],['distance','NEAREST'],['rating','RESTAURANT RATING'],['name','NAME A → Z']
  ] : [
    ['distance','NEAREST'],['value','VALUE SCORE'],['deal_density','DEAL DENSITY'],['rating','TOP RATED'],['reviews','MOST REVIEWED'],['delivery','FASTEST'],['fee','LOWEST FEE'],['menu_size','BIGGEST MENU'],['name','NAME A → Z']
  ];
  if(!options.some(([v])=>v===state.sort))state.sort=options[0][0];
  $('sortSelect').innerHTML=options.map(([v,l])=>`<option value="${v}" ${v===state.sort?'selected':''}>${l}</option>`).join('');
}

function renderAll() { updateStats(); if(state.view==='analytics')renderAnalytics(); else renderGrid(); updateCounters(); }
function currentRestaurants() { return (state.restsByLoc[state.location]||[]).map(k=>state.restaurantMap.get(k)); }
function currentDishes() { return (state.dishesByLoc[state.location]||[]).map(k=>state.dishMap.get(k)); }
function currentLocationName(){return state.locations[state.location]?.name||'—';}

function getDhakaNow() {
  const parts = new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Dhaka',weekday:'long',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date());
  const get=(t)=>parts.find(p=>p.type===t)?.value;
  return {day:get('weekday'),minutes:num(get('hour'))*60+num(get('minute'))};
}
function timeMin(value){if(!value)return null;const [h,m]=String(value).split(':').map(Number);return h*60+m;}
function openStatus(r) {
  const now=getDhakaNow(); const row=(r.workingHours||[]).find(x=>String(x.dayName).toLowerCase()===String(now.day).toLowerCase());
  if(!row||row.isClose)return {open:false,closing:false,label:'CLOSED',minutesToClose:null};
  let start=timeMin(row.openTime),end=timeMin(row.closeTime),current=now.minutes;
  if(start===null||end===null)return {open:false,closing:false,label:'HOURS UNKNOWN',minutesToClose:null};
  if(end<=start){end+=1440;if(current<start)current+=1440;}
  let open=current>=start&&current<=end;
  for(let i=1;i<=2;i++){const bs=timeMin(row[`breakTimeStart${i}`]),be=timeMin(row[`breakTimeEnd${i}`]);if(bs!==null&&be!==null&&current>=bs&&current<=be)open=false;}
  const left=end-current; return {open,closing:open&&left<=60,label:open?(left<=60?`CLOSES IN ${left}M`:'OPEN NOW'):`OPENS ${formatTime(row.openTime)}`,minutesToClose:left};
}
function formatTime(value){if(!value)return'—';let [h,m]=value.split(':').map(Number);const a=h>=12?'PM':'AM';h=h%12||12;return`${h}:${String(m).padStart(2,'0')} ${a}`;}

function passesRestaurantFilters(r) {
  if(state.query&&!r.search.includes(state.query))return false;
  if(state.cuisine&&!r.cuisines.includes(state.cuisine))return false;
  if(r.rating<state.minRating||r.deliveryCharge>state.maxFee||r.distance>state.maxDistance)return false;
  if(state.filters.has('favorites')&&!state.favorites.has(r.key))return false;
  if(state.filters.has('open')||state.filters.has('closing')){
    const os=openStatus(r);
    if(state.filters.has('open')&&!os.open)return false;
    if(state.filters.has('closing')&&!os.closing)return false;
  }
  if(state.filters.has('fast')&&r.deliveryTime>15)return false;
  if(state.filters.has('lowfee')&&r.deliveryCharge>40)return false;
  if(state.filters.has('preorder')&&!r.preorder)return false;
  if(state.filters.has('pickup')&&r.pickupTime<=0)return false;
  if(state.filters.has('photo')&&r.photoCoverage<.7)return false;
  if(state.filters.has('custom')&&(r.variationCount+r.addonCount)===0)return false;
  if(state.filters.has('dealstorm')&&!(r.dealDensity>=.5||r.avgDiscount>=20))return false;
  return true;
}
function passesDishFilters(d) {
  const r=state.restaurantMap.get(d.restKey); if(!r)return false;
  if(state.query&&!d.search.includes(state.query))return false;
  if(state.cuisine&&!r.cuisines.includes(state.cuisine)&&d.category!==state.cuisine)return false;
  if(r.rating<state.minRating||r.deliveryCharge>state.maxFee||r.distance>state.maxDistance)return false;
  if(state.filters.has('favorites')&&!state.favorites.has(d.key))return false;
  if(state.filters.has('open')||state.filters.has('closing')){
    const os=openStatus(r);
    if(state.filters.has('open')&&!os.open)return false;if(state.filters.has('closing')&&!os.closing)return false;
  }
  if(state.filters.has('fast')&&r.deliveryTime>15)return false;if(state.filters.has('lowfee')&&r.deliveryCharge>40)return false;
  if(state.filters.has('preorder')&&!r.preorder)return false;if(state.filters.has('pickup')&&r.pickupTime<=0)return false;
  if(state.filters.has('photo')&&!d.image&&!d.banner)return false;if(state.filters.has('custom')&&!d.hasVariation&&!d.hasAddons)return false;
  if(state.filters.has('dealstorm')&&priceMetrics(d).dealPct<20)return false;
  const metric=priceMetrics(d);
  if(state.priceFilters.has('great_deal')&&metric.dealPct<15)return false;
  if(state.priceFilters.has('good_buy')&&metric.dealPct<5)return false;
  if(state.priceFilters.has('custom_change')&&Math.abs(metric.changePct)<state.customChange)return false;
  if(state.priceFilters.has('wait')&&!metric.wait)return false;
  if(state.priceFilters.has('all_time_low')&&!metric.allTimeLow)return false;
  if(state.priceFilters.has('new_items')&&itemAgeDays(d)>state.newDays)return false;
  if(state.priceFilters.has('price_change')&&Math.abs(metric.changePct)<0.001)return false;
  if(state.priceFilters.has('new_range')&&!dateInRange(d.firstSeen,state.newFrom,state.newTo))return false;
  return true;
}
function sortItems(items) {
  const s=state.sort; const copy=[...items];
  copy.sort((a,b)=>{
    if(state.view==='dishes'){
      const am=priceMetrics(a), bm=priceMetrics(b);
      if(s==='price_drop')return am.changePct-bm.changePct;
      if(s==='price_rise')return bm.changePct-am.changePct;
      if(s==='price_change')return Math.abs(bm.changePct)-Math.abs(am.changePct);
      if(s==='newest')return (new Date(b.firstSeen||0))-(new Date(a.firstSeen||0));
      if(s==='price_asc')return a.price-b.price;if(s==='price_desc')return b.price-a.price;if(s==='distance')return a.distance-b.distance;
      if(s==='rating')return b.restaurantRating-a.restaurantRating;if(s==='name')return a.name.localeCompare(b.name);
    }else{
      if(s==='distance')return a.distance-b.distance;if(s==='value')return b.valueScore-a.valueScore;if(s==='deal_density')return b.dealDensity-a.dealDensity;
      if(s==='rating')return b.rating-a.rating;if(s==='reviews')return b.ratingCount-a.ratingCount;if(s==='delivery')return a.deliveryTime-b.deliveryTime;
      if(s==='fee')return a.deliveryCharge-b.deliveryCharge;if(s==='menu_size')return b.menuCount-a.menuCount;if(s==='name')return a.name.localeCompare(b.name);
    }
    return 0;
  }); return copy;
}

function syncLoadAllToggle(){const b=$('loadAllToggle');if(!b)return;b.classList.toggle('active',state.loadAll);b.setAttribute('aria-pressed',String(state.loadAll));$('loadAllState').textContent=state.loadAll?'ON':'OFF';}

function renderGrid(resetScroll=false) {
  if(state.view==='analytics')return;
  const base=state.view==='dishes'?currentDishes():currentRestaurants();
  const filtered=sortItems(base.filter(state.view==='dishes'?passesDishFilters:passesRestaurantFilters)); state.filtered=filtered;
  const visible=state.loadAll?filtered:filtered.slice(0,state.renderLimit);
  $('grid').innerHTML=visible.length?visible.map(state.view==='dishes'?dishCard:restaurantCard).join(''):emptyState();
  const remaining=Math.max(0,filtered.length-visible.length);$('loadMoreBtn').hidden=state.loadAll||remaining===0;syncLoadAllToggle();$('remainingCount').textContent=remaining.toLocaleString();
  $('summaryMode').textContent=state.view.toUpperCase();$('summaryResults').textContent=filtered.length.toLocaleString();$('summarySignal').textContent=activeSignal();
  $('sideVisible').textContent=filtered.length.toLocaleString();updateCounters();if(resetScroll)window.scrollTo({top:0});
}
function activeSignal(){const parts=[...state.filters,...state.priceFilters].map(x=>x.replaceAll('_',' ').toUpperCase());if(state.cuisine)parts.push(state.cuisine.toUpperCase());if(state.query)parts.push(`“${state.query.toUpperCase()}”`);return parts.join(' + ')||'UNFILTERED';}
function emptyState(){return `<div class="empty-state"><b>ZERO BITES FOUND.</b><p>THE FILTER STACK IS TOO VIOLENT.</p><button class="block-btn" data-action="reset">RESET EVERYTHING</button></div>`;}
function imageMarkup(src,alt,kind='') {return src?`<img src="${esc(src)}" alt="${esc(alt)}" loading="lazy" decoding="async" onerror="this.parentElement.classList.add('no-image');this.remove()">`:`<div class="${kind==='dish'?'menu-item-placeholder':''}">${kind==='dish'?'NO IMG':'FE'}</div>`;}
function restaurantCard(r){const os=openStatus(r);return `<article class="card restaurant-card" data-open="${r.key}">
  <div class="card-media ${r.cover?'':'no-image'}">${imageMarkup(r.cover,r.name)}<div class="card-stickers"><div class="sticker-stack"><span class="sticker ${os.open?'cyan':'red'}">${esc(os.label)}</span>${r.dealDensity>=.5?`<span class="sticker pink">${pct(r.dealDensity*100)} DEAL MENU</span>`:''}${r.preorder?'<span class="sticker white">PREORDER</span>':''}</div><button class="heart-btn ${state.favorites.has(r.key)?'active':''}" data-action="favorite" data-key="${r.key}" aria-label="Favorite"><i class="fa-${state.favorites.has(r.key)?'solid':'regular'} fa-heart"></i></button></div></div>
  <div class="card-body"><div class="card-kicker">${esc(r.locationName.toUpperCase())} // ${esc(r.primaryCuisine.toUpperCase())}</div><div class="card-title">${esc(r.name)}</div><div class="card-sub">${esc(r.cuisines.slice(0,4).join(' • '))}</div>
  <div class="card-metrics"><div class="card-metric"><span>RATING</span><b>★ ${r.rating?r.rating.toFixed(1):'—'}</b></div><div class="card-metric"><span>DELIVERY</span><b>${r.deliveryTime} MIN</b></div><div class="card-metric"><span>FEE</span><b>${money(r.deliveryCharge)}</b></div></div>
  <div class="card-metrics"><div class="card-metric"><span>MENU</span><b>${r.menuCount}</b></div><div class="card-metric"><span>DISCOUNTED</span><b>${r.discountedCount}</b></div><div class="card-metric"><span>VALUE</span><b>${Math.round(r.valueScore)}/100</b></div></div></div>
  <div class="card-actions"><button class="primary" data-action="open" data-key="${r.key}">OPEN MENU</button><button class="${isCompared(r.key)?'active':''}" data-action="compare" data-key="${r.key}" title="Compare"><i class="fa-solid fa-code-compare"></i></button><button data-action="random-dish" data-key="${r.key}" title="Random dish"><i class="fa-solid fa-dice"></i></button></div></article>`;}
function dishCard(d){return `<article class="card dish-card dish-card-minimal" data-open-dish="${d.key}" tabindex="0" aria-label="Open ${esc(d.name)} price view">
  <div class="card-media ${d.image||d.banner?'':'no-image'}">${imageMarkup(d.image||d.banner,d.name,'dish')}</div>
  <div class="dish-card-core"><div class="card-title">${esc(d.name)}</div><div class="dish-card-restaurant">${esc(d.restaurantName)}</div><div class="price-now">${money(d.price)}</div></div>
</article>`;}

function handleGridClick(e){const action=e.target.closest('[data-action]');if(action){e.stopPropagation();const key=action.dataset.key;switch(action.dataset.action){case'open':openRestaurant(key);break;case'open-dish':openDish(key);break;case'favorite':toggleFavorite(key);break;case'compare':toggleCompare(key);break;case'cart':addCart(key);break;case'random-dish':openRandomDish(key);break;case'reset':resetFilters();break;}return;}const r=e.target.closest('[data-open]');if(r)openRestaurant(r.dataset.open);const d=e.target.closest('[data-open-dish]');if(d)openDish(d.dataset.openDish);}

function renderCuisineList(){const term=$('sidebarSearch').value.trim().toLowerCase();const counts=new Map();currentRestaurants().forEach(r=>r.cuisines.forEach(c=>counts.set(c,(counts.get(c)||0)+1)));const rows=[...counts.entries()].filter(([c])=>!term||c.toLowerCase().includes(term)).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]));$('cuisineCount').textContent=rows.length;$('cuisineList').innerHTML=`<button class="cuisine-btn ${!state.cuisine?'active':''}" data-cuisine=""><span>ALL CUISINES</span><b>${currentRestaurants().length}</b></button>${rows.map(([c,n])=>`<button class="cuisine-btn ${state.cuisine===c?'active':''}" data-cuisine="${esc(c)}"><span>${esc(c.toUpperCase())}</span><b>${n}</b></button>`).join('')}`;$('sideLocation').textContent=currentLocationName().toUpperCase();}
function updateStats(){const rests=currentRestaurants(),dishes=currentDishes();const open=rests.filter(r=>openStatus(r).open).length;const disc=dishes.filter(d=>d.discountPct>0).length;const avg=rests.length?rests.reduce((s,r)=>s+r.deliveryTime,0)/rests.length:0;$('statRestaurants').textContent=rests.length.toLocaleString();$('statDishes').textContent=dishes.length.toLocaleString();$('statDiscounted').textContent=disc.toLocaleString();$('statOpen').textContent=open.toLocaleString();$('statDelivery').textContent=`${Math.round(avg)}m`;$('statRestaurantsSub').textContent=currentLocationName().toUpperCase();$('statDishesSub').textContent=`${rests.length} MENUS`;$('statDiscountedSub').textContent=`${pct(dishes.length?disc/dishes.length*100:0)} OF DISHES`;$('statOpenSub').textContent='ASIA/DHAKA';$('statDeliverySub').textContent='MENU + DELIVERY SNAPSHOT';}
function updateCounters(){const cartQty=Object.values(state.cart).reduce((s,v)=>s+num(v),0);$('cartCount').textContent=cartQty;$('watchCount').textContent=Object.values(state.watch).filter(a=>a&&a.dishKey&&state.dishMap.has(a.dishKey)).length;$('compareCount').textContent=state.compare.ids.length;$('compareTrayCount').textContent=`${state.compare.ids.length} / 4`;$('sideSaved').textContent=state.favorites.size;$('compareTray').hidden=state.compare.ids.length===0;$('compareTrayItems').innerHTML=state.compare.ids.map(id=>{const item=state.compare.type==='restaurant'?state.restaurantMap.get(id):state.dishMap.get(id);return item?`<button class="compare-pill" data-remove-compare="${id}">${esc(item.name)} ×</button>`:'';}).join('');}

function renderSuggestions(value){const term=String(value||'').trim().toLowerCase();if(term.length<2){hideSuggestions();return;}const rs=currentRestaurants().filter(r=>r.search.includes(term)).slice(0,4);const ds=currentDishes().filter(d=>d.search.includes(term)).slice(0,6);const rows=[...rs.map(r=>({type:'r',key:r.key,name:r.name,sub:`${r.primaryCuisine} • ${r.deliveryTime} min`,img:r.image||r.cover})),...ds.map(d=>({type:'d',key:d.key,name:d.name,sub:`${d.restaurantName} • ${money(d.price)}`,img:d.image||d.banner}))].slice(0,8);if(!rows.length){hideSuggestions();return;}$('suggestions').innerHTML=rows.map(x=>`<button class="suggestion" data-suggest="${x.type}|${x.key}">${x.img?`<img src="${esc(x.img)}" alt="" loading="lazy">`:'<span></span>'}<span><b>${esc(x.name)}</b><br><small>${esc(x.sub)}</small></span><small>${x.type==='r'?'PLACE':'DISH'}</small></button>`).join('');$('suggestions').classList.add('show');}
function hideSuggestions(){$('suggestions').classList.remove('show');}

function toggleFavorite(key){state.favorites.has(key)?state.favorites.delete(key):state.favorites.add(key);writeJSON(STORE.favorites,[...state.favorites]);toast(state.favorites.has(key)?'SAVED TO FAVORITES':'REMOVED FROM FAVORITES','info');renderGrid();}
function favoriteVisible(){state.filtered.slice(0,state.renderLimit).forEach(x=>state.favorites.add(x.key));writeJSON(STORE.favorites,[...state.favorites]);toast('VISIBLE ITEMS SAVED');renderGrid();}
function resetFilters() {state.query='';state.cuisine='';state.minRating=0;state.maxFee=999;state.maxDistance=999;state.filters.clear();state.priceFilters.clear();state.customChange=12;state.newDays=7;state.newFrom='';state.newTo='';state.meanFrom='';state.meanTo='';state.meanVersion++;state.renderLimit=BATCH;$('globalSearch').value='';$('cuisineSelect').value='';$('ratingSelect').value='0';$('feeSelect').value='999';$('distanceSelect').value='999';$('customChangePct').value='12';$('newDays').value='7';['newFrom','newTo','meanFrom','meanTo'].forEach(id=>$(id).value='');qsa('[data-filter],[data-price-filter]').forEach(b=>b.classList.remove('active'));$('favoritesOnlyBtn').classList.remove('active');renderCuisineList();renderGrid();}
function toggleTheme(){const next=document.body.dataset.theme==='ink'?'paper':'ink';document.body.dataset.theme=next;storageSet(STORE.theme,next);toast(`${next.toUpperCase()} PALETTE ACTIVE`,'info');}
function togglePriceFilter(name){
  if(name==='new_range'&&!(state.newFrom||state.newTo)){toast('SET A NEW-ITEM DATE RANGE FIRST','error');return;}
  state.priceFilters.has(name)?state.priceFilters.delete(name):state.priceFilters.add(name);
  qsa(`[data-price-filter="${name}"]`).forEach(b=>b.classList.toggle('active',state.priceFilters.has(name)));
  state.renderLimit=BATCH;renderGrid();
}

function surpriseMe(){if(!state.filtered.length){toast('NO ITEMS TO SURPRISE YOU WITH','error');return;}const item=state.filtered[Math.floor(Math.random()*state.filtered.length)];state.view==='dishes'?openDish(item.key):openRestaurant(item.key);}
function openRandomDish(restKey){const ids=state.dishesByRest.get(restKey)||[];if(!ids.length)return toast('NO MENU DATA','error');openDish(ids[Math.floor(Math.random()*ids.length)]);}

function toggleCompare(key){const type=key.startsWith('r:')?'restaurant':'dish';if(state.compare.type&&state.compare.type!==type){state.compare={type,ids:[]};toast('COMPARE MODE SWITCHED — OLD QUEUE CLEARED','info');}state.compare.type=type;const i=state.compare.ids.indexOf(key);if(i>=0)state.compare.ids.splice(i,1);else if(state.compare.ids.length<4)state.compare.ids.push(key);else return toast('COMPARE LIMIT IS 4','error');writeJSON(STORE.compare,state.compare);updateCounters();renderGrid();}
function removeCompare(key){state.compare.ids=state.compare.ids.filter(x=>x!==key);if(!state.compare.ids.length)state.compare.type='';writeJSON(STORE.compare,state.compare);updateCounters();renderGrid();}
function clearCompare(){state.compare={type:'',ids:[]};writeJSON(STORE.compare,state.compare);updateCounters();renderGrid();}
function isCompared(key){return state.compare.ids.includes(key);}

function addCart(key,qty=1){const d=state.dishMap.get(key);if(!d)return;state.cart[key]=num(state.cart[key])+qty;if(state.cart[key]<=0)delete state.cart[key];writeJSON(STORE.cart,state.cart);updateCounters();toast(`${d.name.toUpperCase()} ADDED TO CART`);}
function addAlert(key,direction){
  const d=state.dishMap.get(key);if(!d)return;
  const threshold=clamp(state.customChange||12,1,95);const alertKey=`${key}|${direction}`;
  state.watch[alertKey]={dishKey:key,direction,threshold,baseline:d.price,createdAt:new Date().toISOString()};
  writeJSON(STORE.watch,state.watch);updateCounters();toast(`${direction.toUpperCase()} ALERT SET AT ${threshold}% FOR ${d.name.toUpperCase()}`,'info');
}
function alertChange(alert,d){return alert.baseline>0?(d.price-alert.baseline)/alert.baseline*100:0;}
function checkWatchTargets(){Object.entries(state.watch).forEach(([alertKey,alert])=>{const d=state.dishMap.get(alert?.dishKey);if(!d)return;const change=alertChange(alert,d);const hit=alert.direction==='drop'?change<=-num(alert.threshold):change>=num(alert.threshold);if(hit)toast(`${alert.direction.toUpperCase()} ALERT: ${d.name} ${change>0?'+':''}${change.toFixed(1)}%`,'info');});}

function openRestaurant(key){const r=state.restaurantMap.get(key);if(!r)return;const os=openStatus(r);const schedule=(r.workingHours||[]).map(row=>`<div class="schedule-row ${String(row.dayName).toLowerCase()===String(getDhakaNow().day).toLowerCase()?'today':''}"><b>${esc(row.dayName||'—')}</b><span>${row.isClose?'CLOSED':`${formatTime(row.openTime)} — ${formatTime(row.closeTime)}`}</span></div>`).join('');
  const dishes=(r.dishKeys||[]).map(k=>state.dishMap.get(k)).filter(Boolean);const groups=new Map();dishes.forEach(d=>{if(!groups.has(d.category))groups.set(d.category,[]);groups.get(d.category).push(d);});
  $('detailContent').innerHTML=`<section class="detail-hero" style="background-image:url('${esc(r.cover||r.image)}')"><div class="detail-hero-copy"><div class="eyebrow">${esc(r.locationName.toUpperCase())} // ${esc(os.label)}</div><h2>${esc(r.name)}</h2><p>${esc(r.cuisines.join(' • '))}</p></div></section>
  <section class="detail-stat-strip"><div class="detail-stat"><span>RATING</span><b>★ ${r.rating?r.rating.toFixed(2):'—'} (${r.ratingCount})</b></div><div class="detail-stat"><span>DELIVERY</span><b>${r.deliveryTime} MIN</b></div><div class="detail-stat"><span>FEE</span><b>${money(r.deliveryCharge)}</b></div><div class="detail-stat"><span>MIN ORDER</span><b>${money(r.minOrder)}</b></div><div class="detail-stat"><span>RADIUS</span><b>${r.deliveryRadius>0?r.deliveryRadius+' KM':'—'}</b></div><div class="detail-stat"><span>VALUE SCORE</span><b>${Math.round(r.valueScore)}/100</b></div></section>
  <div class="detail-toolbar"><button class="block-btn" data-modal-action="favorite" data-key="${r.key}"><i class="fa-solid fa-heart"></i> ${state.favorites.has(r.key)?'SAVED':'SAVE'}</button><button class="block-btn" data-modal-action="compare" data-key="${r.key}"><i class="fa-solid fa-code-compare"></i> COMPARE</button><button class="block-btn" data-modal-action="random-dish" data-key="${r.key}"><i class="fa-solid fa-dice"></i> RANDOM DISH</button><span class="block-btn acid">${r.discountedCount}/${r.menuCount} DISCOUNTED</span></div>
  <section class="detail-grid"><aside class="detail-aside"><h3>OPERATING FILE</h3><div class="data-list"><div class="data-row"><span>PREORDER</span><b>${r.preorder?'YES':'NO'}</b></div><div class="data-row"><span>PICKUP TIME</span><b>${r.pickupTime?r.pickupTime+' MIN':'N/A'}</b></div><div class="data-row"><span>PHOTO COVERAGE</span><b>${pct(r.photoCoverage*100)}</b></div><div class="data-row"><span>AVG DISCOUNT</span><b>${pct(r.avgDiscount)}</b></div><div class="data-row"><span>CUSTOMIZABLE</span><b>${r.variationCount+r.addonCount}</b></div></div><h3>TODAY + WEEK</h3><div class="schedule-table">${schedule||'<p>NO HOURS DATA</p>'}</div></aside>
  <div class="menu-zone"><div class="menu-head"><h3>MENU / ${dishes.length}</h3><input id="modalMenuSearch" class="menu-search" type="search" placeholder="SEARCH THIS MENU…"></div><div id="modalMenuGroups">${menuGroupsMarkup(groups)}</div></div></section>`;
  openModal(); setTimeout(()=>{$('modalMenuSearch')?.addEventListener('input',debounce((e)=>filterModalMenu(r,e.target.value),80));},0);
}
function menuGroupsMarkup(groups){return [...groups.entries()].map(([cat,items])=>`<section class="menu-category"><h4>${esc(cat.toUpperCase())} / ${items.length}</h4><div class="menu-items">${items.map(d=>`<article class="menu-item minimal-menu-item" data-modal-action="open-dish" data-key="${d.key}">${d.image||d.banner?`<img src="${esc(d.image||d.banner)}" alt="${esc(d.name)}" loading="lazy" decoding="async">`:'<div class="menu-item-placeholder">FE</div>'}<div class="menu-item-copy"><b>${esc(d.name)}</b></div><div class="menu-item-price"><b>${money(d.price)}</b></div></article>`).join('')}</div></section>`).join('');}
function filterModalMenu(r,value){const term=value.trim().toLowerCase();const dishes=(r.dishKeys||[]).map(k=>state.dishMap.get(k)).filter(d=>!term||d.search.includes(term));const groups=new Map();dishes.forEach(d=>{if(!groups.has(d.category))groups.set(d.category,[]);groups.get(d.category).push(d);});$('modalMenuGroups').innerHTML=menuGroupsMarkup(groups)||'<div class="empty-state"><b>NO MENU MATCH.</b></div>';}
function openDish(key){
  const d=state.dishMap.get(key);if(!d)return;
  closeModal();
  let keys=[];
  if(state.view==='dishes'&&state.filtered.some(item=>item.key===key))keys=state.filtered.map(item=>item.key);
  if(!keys.length)keys=(state.dishesByRest.get(d.restKey)||[]).filter(id=>state.dishMap.has(id));
  state.viewerKeys=keys.length?keys:[key];state.viewerIndex=Math.max(0,state.viewerKeys.indexOf(key));state.viewerKey=key;
  $('dishViewer').classList.add('open');$('dishViewer').setAttribute('aria-hidden','false');document.body.style.overflow='hidden';renderDishViewer();
}
function renderDishViewer(){
  const d=state.dishMap.get(state.viewerKey);if(!d)return closeDishViewer();
  const r=state.restaurantMap.get(d.restKey);const metric=priceMetrics(d);const changeClass=metric.changePct<0?'down':metric.changePct>0?'up':'flat';
  const image=d.banner||d.image||'';$('dishViewerStage').style.setProperty('--dish-bg',image?`url("${image.replaceAll('"','%22')}")`:'none');
  const firstSeen=d.firstSeen?dateLabel(d.firstSeen):'UNKNOWN';const meanCopy=metric.mean?money(metric.mean):'NO SERIES';
  const previousCopy=metric.previous?money(metric.previous):'—';const changeCopy=metric.previous?`${metric.change>=0?'+':''}${money(metric.change)} / ${metric.changePct>=0?'+':''}${metric.changePct.toFixed(1)}%`:'—';
  $('dishViewerHeader').innerHTML=`<div class="viewer-heading"><div class="viewer-kicker">${esc(d.category.toUpperCase())} // ${esc(r.name.toUpperCase())}</div><h2>${esc(d.name)}</h2><p>${esc(d.description||'NO DESCRIPTION IN DATASET')}</p></div>
  <div class="viewer-price-block"><span>CURRENT PRICE</span><b>${money(d.price)}</b>${d.oldPrice>0?`<small>OLD/LIST ${money(d.oldPrice)}</small>`:''}</div>
  <div class="viewer-metrics"><div><span>CHANGE</span><b class="${changeClass}">${changeCopy}</b></div><div><span>PREVIOUS</span><b>${previousCopy}</b></div><div><span>MEAN</span><b>${meanCopy}</b></div><div><span>KNOWN LOW</span><b>${d.hasHistory?money(metric.fullMin):'NO SERIES'}</b></div><div><span>FIRST SEEN</span><b>${firstSeen}</b></div><div><span>RESTAURANT</span><b>★ ${r.rating?r.rating.toFixed(1):'—'} / ${r.deliveryTime}M / ${money(r.deliveryCharge)} FEE</b></div></div>
  <div class="viewer-actions"><button data-viewer-action="alert-drop"><i class="fa-solid fa-arrow-trend-down"></i> DROP ${state.customChange}%</button><button data-viewer-action="alert-rise"><i class="fa-solid fa-arrow-trend-up"></i> RISE ${state.customChange}%</button><button class="${isCompared(d.key)?'active':''}" data-viewer-action="compare"><i class="fa-solid fa-code-compare"></i> COMPARE</button><button class="acid" data-viewer-action="cart"><i class="fa-solid fa-cart-plus"></i> CART</button><button data-viewer-action="restaurant"><i class="fa-solid fa-store"></i> RESTAURANT</button></div>`;
  $('viewerPosition').textContent=`${state.viewerIndex+1} / ${state.viewerKeys.length}`;$('historySource').textContent=d.historySource;
  const realCount=d.history.length;$('historyEmpty').hidden=realCount>=2;
  $('historyEmpty').innerHTML=realCount===1?`<b>ONE REAL SNAPSHOT.</b><span>${dateLabel(d.history[0].date)} // ${money(d.history[0].price)}</span><small>A TREND LINE NEEDS AT LEAST TWO DATED RECORDS.</small>`:`<b>NO PRICE HISTORY.</b><small>THIS DATASET HAS NO DATED RECORDS FOR THIS ITEM.</small>`;
  requestAnimationFrame(drawPriceHistory);
}
function drawPriceHistory(){
  const d=state.dishMap.get(state.viewerKey),canvas=$('priceHistoryCanvas'),wrap=$('historyPlot');if(!d||!canvas||!wrap)return;
  const rect=wrap.getBoundingClientRect(),ratio=Math.min(window.devicePixelRatio||1,1.5);canvas.width=Math.max(1,Math.floor(rect.width*ratio));canvas.height=Math.max(1,Math.floor(rect.height*ratio));canvas.style.width=`${rect.width}px`;canvas.style.height=`${rect.height}px`;
  const ctx=canvas.getContext('2d');ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,rect.width,rect.height);
  const points=d.history;if(!points.length)return;const css=getComputedStyle(document.body),line=css.getPropertyValue('--acid').trim()||'#efff00',grid='rgba(255,255,255,.18)',text=css.getPropertyValue('--text').trim()||'#fff';
  const pad={l:72,r:54,t:Math.min(300,rect.height*.35),b:68},w=Math.max(10,rect.width-pad.l-pad.r),h=Math.max(10,rect.height-pad.t-pad.b);
  const prices=points.map(p=>p.price);let min=Math.min(...prices),max=Math.max(...prices);if(min===max){min*=.9;max*=1.1;if(min===max){min-=1;max+=1;}}
  ctx.lineWidth=1;ctx.strokeStyle=grid;ctx.fillStyle=text;ctx.font='900 11px Arial';ctx.textBaseline='middle';
  for(let i=0;i<5;i++){const y=pad.t+h*i/4;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(pad.l+w,y);ctx.stroke();const value=max-(max-min)*i/4;ctx.fillText(money(value),8,y);}
  const xy=points.map((p,i)=>({x:points.length===1?pad.l+w/2:pad.l+w*i/(points.length-1),y:pad.t+h-(p.price-min)/(max-min)*h,p}));
  if(points.length>1){ctx.strokeStyle=line;ctx.lineWidth=5;ctx.lineJoin='bevel';ctx.beginPath();xy.forEach((pt,i)=>i?ctx.lineTo(pt.x,pt.y):ctx.moveTo(pt.x,pt.y));ctx.stroke();}
  xy.forEach((pt,i)=>{ctx.fillStyle=line;ctx.strokeStyle='#000';ctx.lineWidth=3;ctx.beginPath();ctx.arc(pt.x,pt.y,points.length===1?10:6,0,Math.PI*2);ctx.fill();ctx.stroke();if(i===0||i===xy.length-1){ctx.fillStyle=text;ctx.textAlign=i===0?'left':'right';ctx.fillText(dateLabel(pt.p.date),pt.x,pad.t+h+28);ctx.fillText(money(pt.p.price),pt.x,pt.y-20);}});ctx.textAlign='left';
}
function cycleDish(step){if(!state.viewerKey||!state.viewerKeys.length)return;state.viewerIndex=(state.viewerIndex+step+state.viewerKeys.length)%state.viewerKeys.length;state.viewerKey=state.viewerKeys[state.viewerIndex];renderDishViewer();}
function closeDishViewer(){state.viewerKey='';state.viewerKeys=[];state.viewerIndex=-1;$('dishViewer').classList.remove('open');$('dishViewer').setAttribute('aria-hidden','true');if(!$('detailModal').classList.contains('open'))document.body.style.overflow='';}
function handleViewerAction(e){const b=e.target.closest('[data-viewer-action]');if(!b)return;const d=state.dishMap.get(state.viewerKey);if(!d)return;switch(b.dataset.viewerAction){case'alert-drop':addAlert(d.key,'drop');break;case'alert-rise':addAlert(d.key,'rise');break;case'compare':toggleCompare(d.key);renderDishViewer();break;case'cart':addCart(d.key);break;case'restaurant':closeDishViewer();openRestaurant(d.restKey);break;}}

function openModal(){$('detailModal').classList.add('open');$('detailModal').setAttribute('aria-hidden','false');document.body.style.overflow='hidden';}
function closeModal(){$('detailModal').classList.remove('open');$('detailModal').setAttribute('aria-hidden','true');document.body.style.overflow='';}
function handleModalAction(e){const b=e.target.closest('[data-modal-action]');if(!b)return;const key=b.dataset.key;switch(b.dataset.modalAction){case'favorite':toggleFavorite(key);break;case'compare':toggleCompare(key);break;case'random-dish':closeModal();openRandomDish(key);break;case'open-dish':openDish(key);break;case'cart':addCart(key);break;case'open-restaurant':openRestaurant(key);break;}}

function openDrawer(kicker,title,html){$('drawerKicker').textContent=kicker;$('drawerTitle').textContent=title;$('drawerContent').innerHTML=html;$('drawer').classList.add('open');$('drawerOverlay').classList.add('open');$('drawer').setAttribute('aria-hidden','false');}
function closeDrawer(){$('drawer').classList.remove('open');$('drawerOverlay').classList.remove('open');$('drawer').setAttribute('aria-hidden','true');}
function renderCartDrawer(){const entries=Object.entries(state.cart).filter(([k,q])=>state.dishMap.has(k)&&num(q)>0);if(!entries.length)return openDrawer('BASKET','CART','<div class="empty-state"><b>CART IS EMPTY.</b><p>ADD DISHES FROM THE DEAL PIT.</p></div>');const groups=new Map();entries.forEach(([k,q])=>{const d=state.dishMap.get(k);if(!groups.has(d.restKey))groups.set(d.restKey,[]);groups.get(d.restKey).push([d,num(q)]);});let grand=0;const html=[...groups.entries()].map(([rk,items])=>{const r=state.restaurantMap.get(rk);const subtotal=items.reduce((s,[d,q])=>s+d.price*q,0);const gap=Math.max(0,r.minOrder-subtotal);const delivery=r.deliveryCharge;grand+=subtotal+delivery;return `<section class="cart-group"><h3>${esc(r.name)} // ${money(delivery)} DELIVERY</h3>${items.map(([d,q])=>`<div class="cart-item"><div><b>${esc(d.name)}</b><br><small>${money(d.price)} EACH</small></div><div class="qty-controls"><button data-cart-delta="-1" data-key="${d.key}">−</button><b>${q}</b><button data-cart-delta="1" data-key="${d.key}">+</button></div><b>${money(d.price*q)}</b></div>`).join('')}<div class="data-list"><div class="data-row"><span>SUBTOTAL</span><b>${money(subtotal)}</b></div><div class="data-row"><span>MIN ORDER</span><b>${gap?`${money(gap)} SHORT`:'CLEARED'}</b></div><div class="data-row"><span>WITH DELIVERY</span><b>${money(subtotal+delivery)}</b></div></div></section>`;}).join('');openDrawer('BASKET','CART',`${html}<div class="cart-summary"><div class="line total"><span>EST. GRAND TOTAL</span><b>${money(grand)}</b></div><p>Grouped by restaurant. Delivery is counted once per restaurant. Platform fees and taxes are not included.</p><button class="block-btn" data-drawer-action="clear-cart">CLEAR CART</button></div>`);}
function renderWatchDrawer(){
  const entries=Object.entries(state.watch).filter(([,alert])=>alert&&alert.dishKey&&state.dishMap.has(alert.dishKey));
  const html=entries.length?entries.map(([alertKey,alert])=>{const d=state.dishMap.get(alert.dishKey),change=alertChange(alert,d),hit=alert.direction==='drop'?change<=-num(alert.threshold):change>=num(alert.threshold);return `<article class="watch-card"><h3>${esc(d.name)}</h3><p>${esc(d.restaurantName)} // ${alert.direction.toUpperCase()} ≥ ${num(alert.threshold)}% ${hit?'<b>— TRIGGERED</b>':''}</p><div class="data-list"><div class="data-row"><span>BASELINE</span><b>${money(alert.baseline)}</b></div><div class="data-row"><span>CURRENT</span><b>${money(d.price)}</b></div><div class="data-row"><span>CHANGE</span><b>${change>=0?'+':''}${change.toFixed(1)}%</b></div></div><div class="target-row"><input type="number" value="${num(alert.threshold)}" min="1" max="95" data-alert-threshold="${esc(alertKey)}"><button class="block-btn mini" data-alert-save="${esc(alertKey)}">UPDATE</button><button class="block-btn mini" data-alert-remove="${esc(alertKey)}"><i class="fa-solid fa-trash"></i></button></div></article>`;}).join(''):'<div class="empty-state"><b>NO ALERTS.</b><p>OPEN A DISH AND SET A DROP OR RISE ALERT.</p></div>';
  openDrawer('LOCAL PRICE SIGNALS','DROP / RISE ALERTS',`${html}<p><small>Alerts compare future loaded prices with the saved baseline. Background monitoring requires a server.</small></p>`);
}
function renderCompareDrawer(){if(!state.compare.ids.length)return openDrawer('SIDE BY SIDE','COMPARE','<div class="empty-state"><b>QUEUE IS EMPTY.</b><p>ADD 2–4 ITEMS.</p></div>');const items=state.compare.ids.map(id=>state.compare.type==='restaurant'?state.restaurantMap.get(id):state.dishMap.get(id)).filter(Boolean);const cols=items.length;let html;if(state.compare.type==='restaurant'){html=`<div class="compare-grid" style="--compare-cols:${cols}">${items.map(r=>`<section class="compare-col">${r.cover?`<img src="${esc(r.cover)}" alt="${esc(r.name)}">`:''}<h3>${esc(r.name)}</h3>${[['VALUE',Math.round(r.valueScore)+'/100'],['RATING',r.rating?r.rating.toFixed(2):'—'],['REVIEWS',r.ratingCount],['DELIVERY',r.deliveryTime+' MIN'],['FEE',money(r.deliveryCharge)],['MIN ORDER',money(r.minOrder)],['DISTANCE',r.distance.toFixed(2)+' KM'],['MENU',r.menuCount],['DEAL DENSITY',pct(r.dealDensity*100)],['PHOTO COVERAGE',pct(r.photoCoverage*100)],['CUSTOMIZABLE',r.variationCount+r.addonCount]].map(([a,b])=>`<div class="compare-row"><span>${a}</span><b>${b}</b></div>`).join('')}</section>`).join('')}</div>`;}else{html=`<div class="compare-grid" style="--compare-cols:${cols}">${items.map(d=>`<section class="compare-col">${d.image||d.banner?`<img src="${esc(d.image||d.banner)}" alt="${esc(d.name)}">`:''}<h3>${esc(d.name)}</h3>${[['RESTAURANT',d.restaurantName],['PRICE',money(d.price)],['OLD PRICE',d.oldPrice?money(d.oldPrice):'—'],['DISCOUNT',pct(d.discountPct)],['ETA',d.deliveryTime+' MIN'],['DISTANCE',d.distance.toFixed(2)+' KM'],['VARIATIONS',d.hasVariation?'YES':'NO'],['ADD-ONS',d.hasAddons?'YES':'NO']].map(([a,b])=>`<div class="compare-row"><span>${a}</span><b>${esc(b)}</b></div>`).join('')}</section>`).join('')}</div>`;}openDrawer('SIDE BY SIDE',`${state.compare.type.toUpperCase()} COMPARE`,html);}
function handleDrawerClick(e){
  const delta=e.target.closest('[data-cart-delta]');if(delta){addCart(delta.dataset.key,num(delta.dataset.cartDelta));renderCartDrawer();return;}
  const save=e.target.closest('[data-alert-save]');if(save){const key=save.dataset.alertSave,input=$('drawerContent').querySelector(`[data-alert-threshold="${CSS.escape(key)}"]`);if(input&&state.watch[key]){state.watch[key].threshold=clamp(num(input.value)||12,1,95);writeJSON(STORE.watch,state.watch);toast('ALERT THRESHOLD UPDATED','info');renderWatchDrawer();}return;}
  const remove=e.target.closest('[data-alert-remove]');if(remove){delete state.watch[remove.dataset.alertRemove];writeJSON(STORE.watch,state.watch);updateCounters();renderWatchDrawer();return;}
  const clear=e.target.closest('[data-drawer-action="clear-cart"]');if(clear){state.cart={};writeJSON(STORE.cart,state.cart);updateCounters();renderCartDrawer();}
}

function renderAnalytics(){if(!state.analyticsDirty&&!$('analytics').hidden)return;state.analyticsDirty=false;const rests=currentRestaurants(),dishes=currentDishes(),discounted=dishes.filter(d=>d.discountPct>0);const totalSaving=discounted.reduce((s,d)=>s+d.saving,0);const customizable=dishes.filter(d=>d.hasVariation||d.hasAddons).length;const photo=dishes.filter(d=>d.image||d.banner).length;$('analyticsHero').innerHTML=[['SNAPSHOT SAVINGS',money(totalSaving)],['CUSTOMIZABLE',customizable.toLocaleString()],['DISH PHOTO RATE',pct(dishes.length?photo/dishes.length*100:0)],['OPEN NOW',rests.filter(r=>openStatus(r).open).length]].map(([a,b])=>`<div class="hero-metric"><span>${a}</span><b>${b}</b></div>`).join('');
  $('locationBoard').className='location-board';$('locationBoard').innerHTML=state.locations.map((loc,i)=>{const rs=(state.restsByLoc[i]||[]).map(k=>state.restaurantMap.get(k)),ds=(state.dishesByLoc[i]||[]).map(k=>state.dishMap.get(k));const avgRating=avg(rs.filter(r=>r.rating).map(r=>r.rating)),avgFee=avg(rs.map(r=>r.deliveryCharge));return `<section class="location-score"><h4>${esc(loc.name.toUpperCase())}</h4><div class="metric-grid"><div class="metric-cell"><span>RESTAURANTS</span><b>${rs.length}</b></div><div class="metric-cell"><span>DISHES</span><b>${ds.length}</b></div><div class="metric-cell"><span>AVG ★</span><b>${avgRating.toFixed(2)}</b></div></div><div class="metric-grid"><div class="metric-cell"><span>AVG FEE</span><b>${money(avgFee)}</b></div><div class="metric-cell"><span>DISCOUNTS</span><b>${ds.filter(d=>d.discountPct>0).length}</b></div><div class="metric-cell"><span>OPEN NOW</span><b>${rs.filter(r=>openStatus(r).open).length}</b></div></div></section>`;}).join('');
  const cuisineCounts=new Map();rests.forEach(r=>r.cuisines.forEach(c=>cuisineCounts.set(c,(cuisineCounts.get(c)||0)+1)));renderBars('cuisineBars',[...cuisineCounts.entries()].sort((a,b)=>b[1]-a[1]).slice(0,10));
  const ladder=[['30%+ OFF',dishes.filter(d=>d.discountPct>=30).length],['20–29% OFF',dishes.filter(d=>d.discountPct>=20&&d.discountPct<30).length],['15–19% OFF',dishes.filter(d=>d.discountPct>=15&&d.discountPct<20).length],['1–14% OFF',dishes.filter(d=>d.discountPct>0&&d.discountPct<15).length],['NO DISCOUNT',dishes.filter(d=>d.discountPct===0).length]];renderBars('discountLadder',ladder);
  $('customStats').innerHTML=dataList([['VARIATION DISHES',dishes.filter(d=>d.hasVariation).length],['ADD-ON DISHES',dishes.filter(d=>d.hasAddons).length],['BOTH CAPABILITIES',dishes.filter(d=>d.hasVariation&&d.hasAddons).length],['POPULAR DISH FLAGS',dishes.filter(d=>d.isPopular).length],['DISH DESCRIPTIONS',dishes.filter(d=>d.description).length]]);
  $('opsStats').innerHTML=dataList([['AVG DELIVERY',`${Math.round(avg(rests.map(r=>r.deliveryTime)))} MIN`],['AVG DELIVERY FEE',money(avg(rests.map(r=>r.deliveryCharge)))],['AVG MIN ORDER',money(avg(rests.map(r=>r.minOrder)))],['PREORDER ENABLED',rests.filter(r=>r.preorder).length],['PICKUP ENABLED',rests.filter(r=>r.pickupTime>0).length],['HOURS COVERAGE',pct(rests.filter(r=>r.workingHours.length).length/rests.length*100)]]);
  const top=[...rests].sort((a,b)=>b.valueScore-a.valueScore).slice(0,10);$('valueBoard').innerHTML=top.map((r,i)=>`<div class="rank-row"><div class="rank-num">${i+1}</div><div class="rank-name">${esc(r.name)}</div><div><small>VALUE</small><br><b>${Math.round(r.valueScore)}</b></div><div><small>RATING</small><br><b>${r.rating?r.rating.toFixed(1):'—'}</b></div><div><small>DEALS</small><br><b>${pct(r.dealDensity*100)}</b></div><div><small>FEE</small><br><b>${money(r.deliveryCharge)}</b></div></div>`).join('');
  const quality=[['RESTAURANT COVERS',rests.filter(r=>r.cover).length/rests.length],['DISH IMAGES',dishes.filter(d=>d.image||d.banner).length/dishes.length],['DESCRIPTIONS',dishes.filter(d=>d.description).length/dishes.length],['WORKING HOURS',rests.filter(r=>r.workingHours.length).length/rests.length]];$('qualityBoard').innerHTML=`<div class="quality-grid">${quality.map(([a,v])=>`<div class="quality-card"><b>${pct(v*100)}</b><span>${a}</span><div class="bar-track"><div class="bar-fill" style="width:${v*100}%"></div></div></div>`).join('')}</div>`;
}
function avg(arr){return arr.length?arr.reduce((s,v)=>s+num(v),0)/arr.length:0;}
function renderBars(id,rows){const max=Math.max(1,...rows.map(x=>x[1]));$(id).innerHTML=rows.map(([name,value])=>`<div class="bar-row"><div class="bar-label">${esc(String(name).toUpperCase())}</div><div class="bar-track"><div class="bar-fill" style="width:${value/max*100}%"></div></div><b>${Number(value).toLocaleString()}</b></div>`).join('');}
function dataList(rows){return `<div class="data-list">${rows.map(([a,b])=>`<div class="data-row"><span>${esc(a)}</span><b>${esc(b)}</b></div>`).join('')}</div>`;}

function openSidebar(){$('sidebar').classList.add('open');$('sidebarOverlay').classList.add('open');}
function closeSidebar(){$('sidebar').classList.remove('open');$('sidebarOverlay').classList.remove('open');}
function toast(message,type=''){const el=document.createElement('div');el.className=`toast ${type}`;el.textContent=message;$('toastHost').appendChild(el);setTimeout(()=>el.remove(),2800);}
