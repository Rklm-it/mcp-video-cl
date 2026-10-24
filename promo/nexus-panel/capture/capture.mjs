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
const FREEZE = '*,*::before,*::after{animation-play-state:paused!important;animation-delay:0s!important;transition:none!important;caret-color:transparent!important}';

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

fs.writeFileSync(path.join(ROOT, 'src/layout.json'), JSON.stringify(layout, null, 2) + '\n');
console.log(JSON.stringify(layout, (k, v) => (typeof v === 'number' ? Math.round(v) : v)));
await browser.close();
