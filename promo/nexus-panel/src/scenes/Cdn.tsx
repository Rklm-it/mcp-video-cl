// Фишка 01 — маскировка через российские CDN.
// Сверху схема (рисованная, не копия страницы — Q1 это разрешает): телефон →
// российский CDN → нода в Европе; линия прорисовывается (draw-svg-trace),
// по ней бегут пакеты, над первым отрезком загорается «белые списки ✓».
// Снизу — настоящий раздел «Маскировка через CDN»: адреса для клиентов
// въезжают в свои места списка (row-embed, Q9), у каждого «работает».
import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import layout from '../layout.json';
import { CamKey, PageCam, camAt } from '../lib/Cam';
import { EASE, Grain, ramp } from '../lib/Polish';
import { C, FONT, clampOpt } from '../theme';

export const CDN_DURATION = 150;

const PAGE_W = layout.width;
const PAGE_H = layout.cdn.pageH;
const ROWS = layout.cdn.rows;

const CAM_KEYS: CamKey[] = [
  { frame: 0, cx: PAGE_W / 2, cy: 820, zoom: 1.62 },
  { frame: 40, cx: PAGE_W / 2, cy: 780, zoom: 1.7 },
  { frame: CDN_DURATION, cx: PAGE_W / 2, cy: 770, zoom: 1.72 },
];
const EMBED_EASE = Easing.bezier(0.3, 0, 0.25, 1.15);

// схема: три узла по горизонтали
const Y = 790;
const NODES = [
  { x: 170, label: 'Телефон', sub: 'мобильный интернет' },
  { x: 540, label: 'CDN в России', sub: 'Яндекс · Timeweb · Билайн' },
  { x: 910, label: 'Нода', sub: 'в Европе' },
];
const PATH = `M ${NODES[0].x + 70} ${Y} L ${NODES[1].x - 110} ${Y} M ${NODES[1].x + 110} ${Y} L ${NODES[2].x - 70} ${Y}`;
const SEG = NODES[1].x - 110 - (NODES[0].x + 70); // длина одного отрезка

const Icon: React.FC<{ kind: number }> = ({ kind }) => {
  if (kind === 0) {
    return (
      <svg width={64} height={100} viewBox="0 0 64 100"><rect x={4} y={4} width={56} height={92} rx={12} fill="none" stroke={C.text} strokeWidth={5} /><rect x={24} y={84} width={16} height={4} rx={2} fill={C.text} /></svg>
    );
  }
  if (kind === 1) {
    return (
      <div style={{ padding: '18px 26px', borderRadius: 22, background: 'rgba(40,24,74,0.95)', border: `3px solid ${C.logo}`, boxShadow: `0 0 34px rgba(232,121,249,0.45)`, fontSize: 40, fontWeight: 900, color: C.text, whiteSpace: 'nowrap' }}>
        🇷🇺 CDN
      </div>
    );
  }
  return (
    <svg width={90} height={96} viewBox="0 0 90 96">
      {[0, 1, 2].map((r) => (
        <g key={r}><rect x={5} y={5 + r * 30} width={80} height={26} rx={6} fill="none" stroke={C.text} strokeWidth={4.5} /><circle cx={20} cy={18 + r * 30} r={4} fill={C.ok} /></g>
      ))}
    </svg>
  );
};

export const Cdn: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = camAt(CAM_KEYS, frame);

  const nodeIn = (i: number) => ramp(frame, 4 + i * 5, 12, EASE.overshoot);
  const draw = (i: number) => ramp(frame, 16 + i * 10, 16, EASE.out);
  const gate = ramp(frame, 44, 12, EASE.overshoot);
  const pk = (interpolate(frame, [48, CDN_DURATION], [0, 3], clampOpt)) % 1; // целое число кругов — пакет не застывает посреди пути

  return (
    <AbsoluteFill style={{ background: `linear-gradient(160deg, ${C.bg} 0%, ${C.bg2} 55%, #0f0828 100%)` }}>
      <PageCam src="textures/cdn-empty.png" pageW={PAGE_W} pageH={PAGE_H} cam={cam} windowed>
        {ROWS.map((r, i) => {
          const cue = 56 + i * 8;
          if (frame < cue) return null;
          const t = interpolate(frame, [cue, cue + 12], [0, 1], { ...clampOpt, easing: EMBED_EASE });
          const air = 1 - Math.min(1, t);
          return (
            <div
              key={r.file}
              style={{
                position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, borderRadius: 8, overflow: 'hidden',
                transform: `translateX(${(260 * (1 - t)).toFixed(2)}px) scale(${(1 + 0.04 * air).toFixed(4)})`, opacity: Math.min(1, t * 3),
                boxShadow: `0 ${(2 + 12 * air).toFixed(1)}px ${(6 + 22 * air).toFixed(1)}px rgba(4,2,12,${(0.3 + 0.2 * air).toFixed(3)})`,
              }}
            >
              <Img src={staticFile(`textures/${r.file}`)} style={{ width: '100%', height: '100%', display: 'block' }} />
            </div>
          );
        })}
      </PageCam>

      {/* схема */}
      <AbsoluteFill style={{ pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', left: 0, right: 0, top: Y - 200, height: 400, background: 'linear-gradient(180deg, rgba(11,8,32,0.6) 0%, rgba(11,8,32,0.96) 20%, rgba(11,8,32,0.96) 82%, rgba(11,8,32,0) 100%)' }} />
        <svg width={1080} height={1920} style={{ position: 'absolute', inset: 0 }}>
          <defs>
            <linearGradient id="cdn-line" x1="0" x2="1"><stop offset="0" stopColor={C.logo} /><stop offset="1" stopColor={C.cyan} /></linearGradient>
          </defs>
          {[0, 1].map((i) => {
            const x0 = i === 0 ? NODES[0].x + 70 : NODES[1].x + 110;
            return (
              <line key={i} x1={x0} y1={Y} x2={x0 + SEG * draw(i)} y2={Y} stroke="url(#cdn-line)" strokeWidth={6} strokeLinecap="round" style={{ filter: 'drop-shadow(0 0 8px rgba(232,121,249,0.6))' }} />
            );
          })}
          {frame >= 48 && [0, 1].map((i) => {
            const x0 = i === 0 ? NODES[0].x + 70 : NODES[1].x + 110;
            const u = (pk + i * 0.5) % 1;
            const a = 1 - Math.abs(u - 0.5) * 1.4;
            return <circle key={`pk${i}`} cx={x0 + SEG * u} cy={Y} r={10} fill="#fff" opacity={a} style={{ filter: `drop-shadow(0 0 10px ${C.pink})` }} />;
          })}
          <path d={PATH} fill="none" stroke="transparent" />
        </svg>
        {NODES.map((n, i) => {
          const t = nodeIn(i);
          return (
            <div key={i} style={{ position: 'absolute', left: n.x - 200, width: 400, top: Y - 70, display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: Math.min(1, t * 2), transform: `scale(${(0.7 + 0.3 * t).toFixed(4)})`, fontFamily: FONT }}>
              <div style={{ height: 140, display: 'flex', alignItems: 'center' }}><Icon kind={i} /></div>
              <div style={{ marginTop: 10, fontSize: 38, fontWeight: 800, color: C.text }}>{n.label}</div>
              <div style={{ fontSize: 28, fontWeight: 500, color: C.text2 }}>{n.sub}</div>
            </div>
          );
        })}
        {/* белые списки пропускают: российский адрес */}
        <div
          style={{
            position: 'absolute', left: (NODES[0].x + NODES[1].x) / 2 - 150, width: 300, top: Y - 130, display: 'flex', justifyContent: 'center',
            opacity: Math.min(1, gate * 2), transform: `translateY(${((1 - gate) * 16).toFixed(2)}px) scale(${(0.8 + 0.2 * gate).toFixed(4)})`, fontFamily: FONT,
          }}
        >
          <span style={{ padding: '8px 18px', borderRadius: 999, background: 'rgba(16,60,44,0.92)', border: `2px solid ${C.ok}`, color: C.ok, fontSize: 30, fontWeight: 800, whiteSpace: 'nowrap' }}>
            ✓ белые списки
          </span>
        </div>
      </AbsoluteFill>
      <Grain opacity={0.05} blend="soft-light" />
    </AbsoluteFill>
  );
};
