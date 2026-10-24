// Съёмка панели Nexus для промо: страницы целиком, вырезки элементов и
// layout.json с координатами (CSS px страницы) — по методу video-shotcraft
// (references/pipeline.md, этап 4).
//
// Ролик вертикальный (1080×1920), поэтому снимается мобильная вёрстка панели:
// окно 540 px CSS — на экране ролика это ровно ×2. Текстуры в 4x (вдвое
// плотнее экрана), карточка, на которую наезжает камера, — в 8x (Q2).
// Фон первого кадра — настольный дашборд.
//
// Панель поднимается на демо-данных (capture/demo-brain.py), тема Nebula.
// Запуск: node capture/capture.mjs [адрес панели] — см. promo/nexus-panel/README.md
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const { chromium } = createRequire(import.meta.url)('playwright');
const BASE = process.argv[2] || 'http://127.0.0.1:3100';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT = path.join(ROOT, 'public/textures');
fs.mkdirSync(OUT, { recursive: true });

const W = 540; // ширина мобильной вёрстки, CSS px
// Анимации — сразу в конечное состояние: на паузе блоки, появившиеся после клика, застывали прозрачными.
const FREEZE = '*,*::before,*::after{animation-duration:0s!important;animation-delay:0s!important;animation-iteration-count:1!important;transition:none!important;caret-color:transparent!important}';

const browser = await chromium.launch();

async function newPage(width, dsf) {
  const ctx = await browser.newContext({ viewport: { width, height: 1080 }, deviceScaleFactor: dsf });
  await ctx.addInitScript(() => {
    localStorage.setItem('admin_token', 'demo');
    localStorage.setItem('admin_login_at', String(Date.now()));
    localStorage.setItem('nexus-theme', 'nebula');
  });
  return ctx.newPage();
}

// Страница на высоту h: окно растягивается, чтобы фиксированные слои шли до
// низа, анимации стоят — кадры совпадают от прогона к прогону.
async function open(page, route, h) {
  await page.goto(BASE + route, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.setViewportSize({ width: page.viewportSize().width, height: h });
  await page.addStyleTag({ content: FREEZE });
  await page.waitForTimeout(1500);
}

// Ближайший предок текста, не меньше minW×minH, — карточка с этой подписью.
async function boxByText(page, text, minW, minH = 80) {
  return page.evaluate(([text, minW, minH]) => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      if (n.textContent.trim() !== text) continue;
      let el = n.parentElement;
      while (el && (el.getBoundingClientRect().width < minW || el.getBoundingClientRect().height < minH)) el = el.parentElement;
      if (!el) continue;
      const r = el.getBoundingClientRect();
      return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height };
    }
    return null;
  }, [text, minW, minH]);
}

// Самый мелкий элемент, чей текст целиком равен text (текст бывает разбит на узлы).
async function boxByElText(page, text) {
  return page.evaluate((text) => {
    const els = [...document.querySelectorAll('body *')].filter((e) => e.textContent.trim() === text);
    if (!els.length) return null;
    const r = els[els.length - 1].getBoundingClientRect();
    return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height };
  }, text);
}

// Строки таблицы шире экрана (таблица листается вбок) — режем по видимой части.
async function boxes(page, selector, maxRight = Infinity) {
  return page.$$eval(selector, (els, maxRight) => els.map((e) => {
    const r = e.getBoundingClientRect();
    return { x: r.x + scrollX, y: r.y + scrollY, w: Math.min(r.width, maxRight - r.x), h: r.height };
  }), maxRight);
}

async function shot(page, file, box) {
  await page.screenshot({ path: path.join(OUT, file), clip: { x: box.x, y: box.y, width: box.w, height: box.h } });
  return { file, ...box };
}

async function full(page, file, h) {
  await page.screenshot({ path: path.join(OUT, file), clip: { x: 0, y: 0, width: page.viewportSize().width, height: h } });
}

async function hide(page, selector) {
  await page.$$eval(selector, (els) => els.forEach((e) => { e.style.visibility = 'hidden'; }));
  await page.waitForTimeout(200);
}

const layout = { width: W };
const page = await newPage(W, 4);

// ── Фон первого кадра: настольный дашборд ──
{
  const desk = await newPage(1920, 1);
  await open(desk, '/', 1080);
  await full(desk, 'desk-dashboard.png', 1080);
  await desk.context().close();
}

// ── Дашборд (мобильный) ──
{
  const H = 1000;
  await open(page, '/', H);
  await full(page, 'dashboard-full.png', H);
  const revenue = await shot(page, 'dash-revenue.png', await boxByText(page, 'Выручка 30д', 200));
  const online = await shot(page, 'dash-online.png', await boxByText(page, 'Онлайн', 200));
  // карточка выручки — герой: камера наезжает на неё, нужна плотность 8x
  const hi = await newPage(W, 8);
  await open(hi, '/', H);
  await hi.screenshot({ path: path.join(OUT, 'dash-revenue-hires.png'), clip: { x: revenue.x, y: revenue.y, width: revenue.w, height: revenue.h } });
  await hi.context().close();
  layout.dashboard = { pageH: H, revenue, online };
}

// ── Серверы ──
{
  const H = 1100;
  await open(page, '/servers', H);
  await full(page, 'servers-full.png', H);
  const tiles = [];
  for (const [i, b] of (await boxes(page, '[data-testid="server-tile"]')).entries()) tiles.push(await shot(page, `node${i + 1}.png`, b));
  const count = await boxByText(page, '9 нод · 9 онлайн', 60, 10);
  await hide(page, '[data-testid="server-tile"]');
  await full(page, 'servers-empty.png', H);
  layout.servers = { pageH: H, tiles, count };
}

// ── Пользователи ──
{
  const H = 1500;
  await open(page, '/users', H);
  await full(page, 'users-full.png', H);
  const search = (await boxes(page, 'input[placeholder="ID или username"]'))[0];
  const count = await boxByElText(page, 'Всего: 1284'); // после фильтра в ролике станет «Найдено: 1»
  const rows = [];
  for (const [i, b] of (await boxes(page, 'tbody tr', W - 17)).slice(0, 12).entries()) rows.push(await shot(page, `user-row${i + 1}.png`, b));
  await hide(page, 'tbody tr');
  await full(page, 'users-empty.png', H);
  layout.users = { pageH: H, search, count, rows, target: 4 }; // ivan_petrov
}

// ── Платежи ──
{
  const H = 1500;
  await open(page, '/payments', H);
  await full(page, 'payments-full.png', H);
  const day = await shot(page, 'pay-day.png', await boxByText(page, 'За сутки', 200));
  const rows = [];
  for (const [i, b] of (await boxes(page, 'tbody tr', W - 17)).slice(0, 8).entries()) rows.push(await shot(page, `pay-row${i + 1}.png`, b));
  await hide(page, 'tbody tr');
  await full(page, 'payments-empty.png', H);
  layout.payments = { pageH: H, day, rows };
}

// ═══ Фишки, которых нет у других (ролик v2) ═══

// Самые глубокие элементы, где есть text, с высотой в [minH, maxH] и шириной ≥ minW.
async function blocksWith(page, text, minH, maxH, minW = 300) {
  return page.evaluate(([text, minH, maxH, minW]) => {
    const hits = [...document.querySelectorAll('body *')].filter((e) => {
      const r = e.getBoundingClientRect();
      return e.textContent.includes(text) && r.height >= minH && r.height <= maxH && r.width >= minW;
    });
    const deepest = hits.filter((e) => !hits.some((o) => o !== e && e.contains(o)));
    return deepest.map((e) => {
      const r = e.getBoundingClientRect();
      return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height };
    }).sort((a, b) => a.y - b.y);
  }, [text, minH, maxH, minW]);
}

async function hideBlocks(page, text, minH, maxH, minW) {
  await page.evaluate(([text, minH, maxH, minW]) => {
    const hits = [...document.querySelectorAll('body *')].filter((e) => {
      const r = e.getBoundingClientRect();
      return e.textContent.includes(text) && r.height >= minH && r.height <= maxH && r.width >= minW;
    });
    hits.filter((e) => !hits.some((o) => o !== e && e.contains(o))).forEach((e) => { e.style.visibility = 'hidden'; });
  }, [text, minH, maxH, minW]);
  await page.waitForTimeout(200);
}

// Тосты «Опознано…» и полоска хода обновления внизу экрана в кадр не нужны.
async function hideToasts(page) {
  await page.evaluate(() => {
    for (const e of document.querySelectorAll('body *')) {
      const s = getComputedStyle(e);
      if (s.position === 'fixed' && e.getBoundingClientRect().top > 300) e.style.visibility = 'hidden';
    }
  });
}

// ── 01. Маскировка через CDN ──
{
  const H = 1250;
  await open(page, '/cdn', H);
  await full(page, 'cdn-full.png', H);
  const rows = [];
  for (const [i, b] of (await blocksWith(page, 'работает', 40, 90, 400)).entries()) rows.push(await shot(page, `cdn-row${i + 1}.png`, b));
  const list = (await blocksWith(page, 'Адреса для клиентов', 200, 600, 400))[0];
  await hideBlocks(page, 'работает', 40, 90, 400);
  await full(page, 'cdn-empty.png', H);
  layout.cdn = { pageH: H, rows, list };
}

// ── 03. Центр состояния и ИИ-разбор ──
{
  const H = 1300;
  await open(page, '/state', H);
  await full(page, 'state-full.png', H);
  const findings = await blocksWith(page, 'Что делать:', 90, 260, 400);
  const service = (await blocksWith(page, 'Есть вопросы', 60, 140, 400))[0];
  const aiTab = (await boxes(page, 'button:has-text("ИИ-разбор")'))[0];
  await page.getByRole('button', { name: 'ИИ-разбор' }).click();
  await page.waitForTimeout(600);
  const analyzeBtn = (await boxes(page, 'button:has-text("Разобрать состояние")'))[0];
  await page.getByRole('button', { name: 'Разобрать состояние' }).click();
  await page.waitForTimeout(1500);
  await full(page, 'ai-full.png', H);
  // строки ответа ИИ — для эффекта печати: маска едет по каждой строке
  const ai = await page.evaluate(() => {
    const p = [...document.querySelectorAll('p')].find((e) => e.textContent.startsWith('1. Сначала'));
    const range = document.createRange();
    range.selectNodeContents(p);
    const lines = [];
    for (const r of range.getClientRects()) {
      const top = Math.round(r.top + scrollY);
      const last = lines[lines.length - 1];
      if (last && Math.abs(last.y - top) < 4) {
        last.w = Math.max(last.x + last.w, r.right) - last.x;
      } else {
        lines.push({ x: r.left + scrollX, y: top, w: r.width, h: r.height });
      }
    }
    const box = p.parentElement.getBoundingClientRect();
    p.style.color = 'transparent';
    return { lines, box: { x: box.x + scrollX, y: box.y + scrollY, w: box.width, h: box.height } };
  });
  await page.waitForTimeout(200);
  await full(page, 'ai-empty.png', H);
  layout.state = { pageH: H, findings, service, ai, aiTab, analyzeBtn };
}

// ── 04. Все ноды обновляются одной кнопкой: четыре шага хода ──
{
  const H = 1150;
  let progress = null;
  await fetch(`${process.env.DEMO_BRAIN || 'http://127.0.0.1:8099'}/__upgrade?step=0`);
  await open(page, '/node-updates', H);
  await hideToasts(page);
  await full(page, 'upd-0.png', H);
  const button = (await boxes(page, 'button:has-text("Обновить все ноды")'))[0];
  for (const step of [1, 2, 3, 4]) {
    await fetch(`${process.env.DEMO_BRAIN || 'http://127.0.0.1:8099'}/__upgrade?step=${step}`);
    await open(page, '/node-updates', H);
    await hideToasts(page);
    await full(page, `upd-${step}.png`, H);
    if (step === 3) progress = (await blocksWith(page, 'Обновление нод', 300, 800, 400))[0];
  }
  await fetch(`${process.env.DEMO_BRAIN || 'http://127.0.0.1:8099'}/__upgrade?step=0`);
  layout.updates = { pageH: H, progress, button };
}

// ── 05. Переезд с другой панели ──
{
  const H = 1300;
  await open(page, '/import', H);
  await full(page, 'import-before.png', H);
  const drop = (await blocksWith(page, 'Файл бэкапа', 80, 300, 400))[0];
  await page.setInputFiles('input[type=file]', { name: 'remnawave-backup.sql.gz', mimeType: 'application/gzip', buffer: Buffer.from('demo') });
  await page.getByRole('button', { name: /Разобрать/ }).click();
  await page.waitForTimeout(1800);
  await hideToasts(page);
  await full(page, 'import-after.png', H);
  const result = (await blocksWith(page, 'Опознано:', 300, 1200, 400))[0];
  const tiles = [];
  for (const [i, label] of ['всего клиентов', 'активных', 'с истёкшим сроком', 'с Telegram ID', 'с UUID'].entries()) {
    const b = (await blocksWith(page, label, 50, 110, 300))[0];
    if (b) tiles.push(await shot(page, `import-tile${i + 1}.png`, b));
  }
  for (const t of tiles) await page.evaluate(({ x, y }) => {
    const e = document.elementFromPoint(x + 4, y + 4 - scrollY);
    let el = e; while (el && el.getBoundingClientRect().height < 50) el = el.parentElement;
    if (el) el.style.visibility = 'hidden';
  }, t);
  await page.waitForTimeout(200);
  await full(page, 'import-after-empty.png', H);
  layout.import = { pageH: H, drop, result, tiles };
}

// ── 02. Маршрутизация ноды: банки — через Россию ──
{
  await open(page, '/servers', 3300);
  await page.getByText('Маршрутизация и DNS', { exact: true }).first().click();
  await page.waitForTimeout(1500);
  await page.addStyleTag({ content: FREEZE });
  const panel = (await blocksWith(page, 'Как работает маршрутизация', 900, 3000, 400))[0];
  const top = Math.floor(panel.y - 70);
  const H = Math.ceil(panel.y + panel.h + 20 - top);
  const shift = (b) => (b ? { ...b, y: b.y - top } : b);
  const chip = async (label) => shift(await boxByElText(page, label));
  const chips = {
    gosuslugi: await chip('🏛️ Госуслуги'),
    telegram: await chip('✈️ Telegram'),
    youtube: await chip('▶️ YouTube'),
    ai: await chip('🤖 Все нейросети'),
  };
  const rules = [];
  for (const [i, b] of (await blocksWith(page, 'domain:', 50, 140, 400)).entries()) {
    rules.push({ ...(await shot(page, `rule${i + 1}.png`, b)), y: b.y - top });
  }
  await page.screenshot({ path: path.join(OUT, 'routing-full.png'), clip: { x: 0, y: top, width: W, height: H } });
  await page.evaluate(() => {
    for (const e of document.querySelectorAll('body *')) {
      const r = e.getBoundingClientRect();
      if (e.textContent.includes('domain:') && r.height >= 50 && r.height <= 140 && r.width >= 400
          && ![...e.children].some((c) => c.textContent.includes('domain:') && c.getBoundingClientRect().height >= 50)) e.style.visibility = 'hidden';
    }
  });
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(OUT, 'routing-norules.png'), clip: { x: 0, y: top, width: W, height: H } });
  layout.routing = { pageH: H, chips, rules };
}

fs.writeFileSync(path.join(ROOT, 'src/layout.json'), JSON.stringify(layout, null, 2) + '\n');
console.log(JSON.stringify(layout, (k, v) => (typeof v === 'number' ? Math.round(v) : v)));
await browser.close();
