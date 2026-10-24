// Живая запись панели Nexus 1920×1080 для обзора на YouTube.
//
// Панель — настоящая (vgx3d/frontend), данные — выдуманные (promo/nexus-panel/capture/demo-brain.py).
// Кадры берём трансляцией Chromium (CDP Page.startScreencast, JPEG 85): встроенная видеозапись
// Playwright жмёт картинку до мыла. Трансляция шлёт кадр только когда экран меняется, поэтому у
// каждого кадра есть метка времени — по ним ffmpeg собирает ровные 30 fps.
//
// Курсора в трансляции нет — рисуем свой (стрелка + рябь на клике), движения плавные, по кривой.
//
// Запуск: node capture/record.mjs <сценарий> [адрес панели]
//   сценарий — имя функции из SCENARIOS ниже (test — пробная запись)
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';
import { fileURLToPath } from 'url';

const { chromium } = createRequire(import.meta.url)('playwright');
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const NAME = process.argv[2] || 'test';
const BASE = process.argv[3] || 'http://127.0.0.1:3100';
// Окно 1280×720 при плотности 1.5 — на выходе те же 1920×1080, но интерфейс крупнее в полтора раза:
// на 1920 CSS-пикселей панель на YouTube читается с трудом (так делают и в скринкастах — масштаб 150%).
const VW = 1280, VH = 720, DPR = 1.5;
const W = VW * DPR, H = VH * DPR, FPS = 30;

// ── курсор и рябь клика, живут в самой странице ──
const CURSOR_JS = () => {
  const install = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div');
    c.id = '__cur';
    c.innerHTML = '<svg width="19" height="28" viewBox="0 0 20 29"><path d="M1 1 L1 23 L6.5 17.5 L10.5 27 L14 25.5 L10 16.5 L18 16.5 Z" fill="#fff" stroke="#120a24" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, { position: 'fixed', left: '0', top: '0', zIndex: 2147483647, pointerEvents: 'none', filter: 'drop-shadow(0 3px 6px rgba(0,0,0,.5))', transform: 'translate(-100px,-100px)', transition: 'none' });
    document.documentElement.appendChild(c);
    const st = document.createElement('style');
    st.textContent = '@keyframes __rip{from{transform:translate(-50%,-50%) scale(.2);opacity:.9}to{transform:translate(-50%,-50%) scale(1);opacity:0}}';
    document.head.appendChild(st);
    window.__curPos = window.__curPos || { x: -100, y: -100 };
    const place = () => { c.style.transform = `translate(${window.__curPos.x}px,${window.__curPos.y}px)`; };
    place();
    document.addEventListener('mousemove', (e) => { window.__curPos = { x: e.clientX, y: e.clientY }; place(); }, true);
    document.addEventListener('mousedown', (e) => {
      c.style.transform += ' scale(.86)';
      for (const [d, size] of [[0, 38], [90, 56]]) {
        setTimeout(() => {
          const r = document.createElement('div');
          Object.assign(r.style, { position: 'fixed', left: e.clientX + 'px', top: e.clientY + 'px', width: size + 'px', height: size + 'px', borderRadius: '50%', border: '2px solid #f0abfc', zIndex: 2147483646, pointerEvents: 'none', animation: '__rip .45s ease-out forwards' });
          document.documentElement.appendChild(r);
          setTimeout(() => r.remove(), 500);
        }, d);
      }
    }, true);
    document.addEventListener('mouseup', place, true);
    // всплывающие подсказки графиков: курсор задевает их по пути, и белый прямоугольник лезет в кадр
    const hideTips = document.createElement('style');
    hideTips.textContent = '.recharts-tooltip-wrapper{display:none!important}';
    document.head.appendChild(hideTips);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install); else install();
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

async function main() {
  const frames = fs.mkdtempSync(path.join(process.env.TMPDIR || '/tmp', 'rec-'));
  // без ограничения частоты кадров трансляция в движении шлёт заметно больше кадров
  const browser = await chromium.launch({ args: ['--disable-gpu-vsync', '--disable-frame-rate-limit'] });
  const ctx = await browser.newContext({ viewport: { width: VW, height: VH }, deviceScaleFactor: DPR });
  await ctx.addInitScript(() => {
    localStorage.setItem('admin_token', 'demo');
    localStorage.setItem('admin_login_at', String(Date.now()));
    localStorage.setItem('nexus-theme', 'nebula');
  });
  await ctx.addInitScript(CURSOR_JS);
  const page = await ctx.newPage();

  // — помощники движения: всё «рукой», с паузами —
  let pos = { x: VW * 0.6, y: VH * 0.55 };
  const moveTo = async (x, y, ms = 700) => {
    const from = { ...pos };
    const bend = { x: (from.x + x) / 2 + (y - from.y) * 0.08, y: (from.y + y) / 2 - (x - from.x) * 0.08 };
    const steps = Math.max(8, Math.round(ms / 16));
    for (let i = 1; i <= steps; i++) {
      const t = ease(i / steps);
      const px = (1 - t) ** 2 * from.x + 2 * (1 - t) * t * bend.x + t * t * x;
      const py = (1 - t) ** 2 * from.y + 2 * (1 - t) * t * bend.y + t * t * y;
      await page.mouse.move(px, py);
      await sleep(16);
    }
    pos = { x, y };
  };
  const box = async (locator) => {
    const l = typeof locator === 'string' ? page.locator(locator).first() : locator;
    await l.scrollIntoViewIfNeeded();
    const b = await l.boundingBox();
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
  };
  const hover = async (locator, ms = 700, pause = 500) => { const p = await box(locator); await moveTo(p.x, p.y, ms); await sleep(pause); };
  const click = async (locator, ms = 700, pause = 600) => {
    const p = await box(locator);
    await moveTo(p.x, p.y, ms);
    await sleep(120);
    await page.mouse.down(); await sleep(90); await page.mouse.up();
    await sleep(pause);
  };
  const type = async (text, delay = 130) => { for (const ch of text) { await page.keyboard.type(ch); await sleep(delay); } };
  const scrollBy = async (dy, ms = 1200) => {
    const steps = Math.round(ms / 16);
    let done = 0;
    for (let i = 1; i <= steps; i++) {
      const target = Math.round(dy * ease(i / steps));
      await page.mouse.wheel(0, target - done);
      done = target;
      await sleep(16);
    }
  };
  const go = async (route) => {
    await page.goto(BASE + route, { waitUntil: 'networkidle' });
    await page.mouse.move(pos.x, pos.y);
    await sleep(400);
  };
  const t = { page, moveTo, hover, click, type, scrollBy, go, sleep, box, W: VW, H: VH };

  // разогрев: открыть первую страницу до старта записи, чтобы не снимать загрузку
  const scenario = SCENARIOS[NAME];
  if (!scenario) throw new Error(`Нет сценария ${NAME}: ${Object.keys(SCENARIOS).join(', ')}`);
  await go(scenario.start);

  // — запись —
  const cdp = await ctx.newCDPSession(page);
  const meta = [];
  let n = 0;
  cdp.on('Page.screencastFrame', async (f) => {
    const file = path.join(frames, `f${String(n++).padStart(6, '0')}.jpg`);
    fs.writeFileSync(file, Buffer.from(f.data, 'base64'));
    meta.push({ file, ts: f.metadata.timestamp });
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 85, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
  const t0 = Date.now();
  await scenario.run(t);
  await sleep(600);
  await cdp.send('Page.stopScreencast');
  const wall = (Date.now() - t0) / 1000;
  await browser.close();

  // — сборка: у каждого кадра длительность до следующего, затем ровные 30 fps —
  const list = path.join(frames, 'list.txt');
  const lines = [];
  for (let i = 0; i < meta.length; i++) {
    const next = i + 1 < meta.length ? meta[i + 1].ts : meta[i].ts + 0.5;
    lines.push(`file '${meta[i].file}'`, `duration ${Math.max(0.001, next - meta[i].ts).toFixed(4)}`);
  }
  lines.push(`file '${meta[meta.length - 1].file}'`);
  fs.writeFileSync(list, lines.join('\n'));
  const outDir = path.join(ROOT, 'out');
  fs.mkdirSync(outDir, { recursive: true });
  const out = path.join(outDir, `rec-${NAME}.mp4`);
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', list,
    '-vf', `fps=${FPS},scale=${W}:${H}:flags=lanczos,format=yuv420p`, '-c:v', 'libx264', '-crf', '16', '-preset', 'slow', out]);
  const span = meta.length > 1 ? meta[meta.length - 1].ts - meta[0].ts : 0;
  console.log(JSON.stringify({ out, frames: meta.length, wall_s: wall.toFixed(1), span_s: span.toFixed(1), avg_fps: (meta.length / span).toFixed(1) }));
  fs.rmSync(frames, { recursive: true, force: true });
}

// ── Сценарии записи. Каждый — то, что видно на экране под один кусок озвучки. ──
const SCENARIOS = {
  // Пробная запись: дашборд → серверы и маршрутизация → поиск клиента → Центр состояния и ИИ-разбор
  test: {
    start: '/',
    async run({ page, hover, click, type, scrollBy, go, sleep, moveTo }) {
      await sleep(800);
      await hover('text=Выручка 30д', 900, 900);
      await hover('text=Онлайн', 700, 700);
      await hover('text=Ноды >> nth=0', 800, 900);
      await click('a:has-text("Серверы (конфиг)")', 900, 1200);
      await hover('[data-testid="server-tile"] >> nth=1', 800, 500);
      await hover('[data-testid="server-tile"] >> nth=5', 700, 700);
      await scrollBy(350, 1300);
      await sleep(500);
      await click('text=Маршрутизация и DNS', 800, 900);
      await scrollBy(380, 1500);
      await hover('text=🏛️ Госуслуги', 800, 700);
      await hover('text=✈️ Telegram', 700, 900);
      await click('a:has-text("Пользователи")', 1000, 1100);
      await click('input[placeholder="ID или username"]', 800, 300);
      await type('ivan');
      await sleep(1400);
      await go('/state');
      await sleep(700);
      await hover('text=Есть вопросы', 800, 700);
      await hover('text=Что делать: >> nth=0', 800, 900);
      await click('button:has-text("ИИ-разбор")', 800, 700);
      await click('button:has-text("Разобрать состояние")', 700, 2400);
      await moveTo(1000, 520, 900);
      await sleep(1600);
    },
  },
};

main().catch((e) => { console.error(e); process.exit(1); });
