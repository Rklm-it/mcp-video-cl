// Ноды: deck-deal-flyin (video-shotcraft, demos/ui-entrance/deck-deal-flyin).
// Колода плиток нод лежит на столе под страницей «Серверы»; облёт колоды →
// замах → плитки, ускоряясь, раздаются в свои настоящие места списка (Q9),
// камера поднимается за раздачей и встаёт фронтально на полный список (Q6).
//
// Из исходника: камера — монотонный сплайн Эрмита (скорость в ключах
// непрерывна), замах колоды 48/30 px, полёт 8f с дугой и пиком 1.06x, посадка
// 4f с перелётом SETTLE_EASE, касание 2f, след, свет разгорается от колоды.
// Переделано: 9 плиток вместо 26 (ускорение 6f → 1f), вертикальный кадр,
// стол — фиолетовый «Nebula» вместо графита.
import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import layout from '../layout.json';
import { CamSpace, Cam } from '../lib/Cam';
import { EASE, Grain, ramp } from '../lib/Polish';
import { MonoTag } from '../lib/ui';
import { C, clampOpt } from '../theme';

export const NODES_DURATION = 150;

const PAGE_W = layout.width;
const PAGE_H = layout.servers.pageH;
const TILES = layout.servers.tiles;
const N = TILES.length;
const DEAL_START = 36;
const PILE = { x: 16, y: 1200 };
const PILE_CX = PILE.x + TILES[0].w / 2;
const PILE_CY = PILE.y + TILES[0].h / 2;
const STACK_STEP = 3;
const HOVER_H = 28;
const SETTLE_EASE = Easing.bezier(0.3, 0, 0.25, 1.15);
const DIVE_EASE = Easing.bezier(0.3, 0, 0.2, 1);
const ANTICIPATE = { from: 26, to: 36, pileDown: 40, topPull: 26 };

const deal = TILES.map((t, k) => ({
  ...t,
  // интервал раздачи 6f → ~1f: «всё быстрее» (R2)
  cue: DEAL_START + 6 * k - 0.33 * k * (k - 1),
  px: PILE.x + (((k * 7) % 9) - 4) * 1.5,
  py: PILE.y + (((k * 5) % 7) - 3) * 1.5,
  protZ: ((k * 11) % 7) - 3,
  pz: (N - k) * STACK_STEP,
}));
const LAST_LAND = deal[N - 1].cue + 12;

type Key = Omit<Cam, never> & { frame: number };
const ANCHORS: Key[] = [
  { frame: 0, cx: 270, cy: 1235, zoom: 2.6, rotX: 32, rotY: -20, rotZ: 6, persp: 1300 },
  { frame: 30, cx: 282, cy: 1215, zoom: 2.45, rotX: 28, rotY: 16, rotZ: -4, persp: 1300 },
  { frame: 64, cx: 270, cy: 780, zoom: 1.72, rotX: 20, rotY: 0, rotZ: 1, persp: 1700 },
  { frame: 100, cx: 270, cy: 640, zoom: 1.94, rotX: 5, rotY: 0, rotZ: 0, persp: 2400 },
  { frame: NODES_DURATION, cx: 270, cy: 640, zoom: 1.97, rotX: 5, rotY: 0, rotZ: 0, persp: 2400 },
];
const PARAMS: (keyof Cam)[] = ['cx', 'cy', 'zoom', 'rotX', 'rotY', 'rotZ', 'persp'];
// монотонный кубический Эрмит (Fritsch–Carlson), как в исходнике
const hermite = (xs: number[], ys: number[]) => {
  const n = xs.length;
  const d = xs.slice(0, -1).map((x, i) => (ys[i + 1] - ys[i]) / (xs[i + 1] - x));
  const m = xs.map((_, i) => (i === 0 ? d[0] : i === n - 1 ? 0 : d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2));
  for (let i = 0; i < n - 1; i++) {
    if (d[i] === 0) { m[i] = 0; m[i + 1] = 0; continue; }
    const a = m[i] / d[i], b = m[i + 1] / d[i], h = a * a + b * b;
    if (h > 9) { const k = 3 / Math.sqrt(h); m[i] = k * a * d[i]; m[i + 1] = k * b * d[i]; }
  }
  return (x: number) => {
    if (x <= xs[0]) return ys[0];
    if (x >= xs[n - 1]) return ys[n - 1];
    let i = 0;
    while (i < n - 2 && x > xs[i + 1]) i++;
    const h = xs[i + 1] - xs[i];
    const t = (x - xs[i]) / h;
    const t2 = t * t, t3 = t2 * t;
    return (2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h * m[i] + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h * m[i + 1];
  };
};
const CURVES = Object.fromEntries(PARAMS.map((p) => [p, hermite(ANCHORS.map((k) => k.frame), ANCHORS.map((k) => k[p]))])) as Record<keyof Cam, (x: number) => number>;
const camAt = (f: number): Cam => Object.fromEntries(PARAMS.map((p) => [p, CURVES[p](f)])) as Cam;

export const Nodes: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = camAt(frame);

  const lightUp = interpolate(frame, [34, 64], [0, 1], { ...clampOpt, easing: Easing.bezier(0.5, 0, 0.6, 1) });
  const holeR = 2200 * lightUp;
  const feather = 300 + 500 * lightUp;
  const antT = interpolate(frame, [ANTICIPATE.from, ANTICIPATE.to], [0, 1], { ...clampOpt, easing: Easing.out(Easing.quad) });
  const landed = deal.filter((c) => frame >= c.cue + 8).length;
  const statIn = ramp(frame, 44, 12, EASE.out);

  // стол — в экранном пространстве: слой стола в 3D под zoom 2.6 весил сотни мегапикселей и ронял вкладку рендера
  const tableBg = [
    `radial-gradient(${900 + 900 * lightUp}px ${700 + 1100 * lightUp}px at 50% ${(72 - 30 * lightUp).toFixed(2)}%, rgba(200,160,255,${(0.2 - 0.08 * lightUp).toFixed(3)}), rgba(160,110,240,0.05) 45%, transparent 70%)`,
    'radial-gradient(circle at 30% 20%, rgba(192,132,252,0.18), transparent 40%)',
    'linear-gradient(135deg, #0b0820 0%, #1a103a 50%, #0f0828 100%)',
  ].join(', ');

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg, overflow: 'hidden' }}>
      <AbsoluteFill style={{ background: tableBg }} />
      <CamSpace cam={cam} pageW={PAGE_W} pageH={PAGE_H}>
        {/* страница-доска с пустыми местами под плитки */}
        <div
          style={{
            position: 'absolute', left: 0, top: 0, width: PAGE_W, height: PAGE_H, overflow: 'hidden', borderRadius: 14,
            boxShadow: '0 0 0 1px rgba(192,132,252,0.22), 0 40px 110px rgba(0,0,0,0.7), 0 0 80px rgba(168,85,247,0.18)',
          }}
        >
          <Img src={staticFile('textures/servers-empty.png')} style={{ position: 'absolute', inset: 0, width: PAGE_W, height: PAGE_H }} />
          {lightUp < 1 && (
            <div
              style={{
                position: 'absolute', inset: 0, background: 'rgba(8,4,20,0.72)',
                WebkitMaskImage: lightUp > 0 ? `radial-gradient(circle at ${PILE_CX}px ${PILE_CY}px, transparent ${holeR.toFixed(0)}px, #000 ${(holeR + feather).toFixed(0)}px)` : undefined,
                maskImage: lightUp > 0 ? `radial-gradient(circle at ${PILE_CX}px ${PILE_CY}px, transparent ${holeR.toFixed(0)}px, #000 ${(holeR + feather).toFixed(0)}px)` : undefined,
              }}
            />
          )}
        </div>

        {deal.map((c, i) => {
          const { cue } = c;
          const diveT = interpolate(frame, [cue, cue + 8], [0, 1], { ...clampOpt, easing: DIVE_EASE });
          const settleT = interpolate(frame, [cue + 8, cue + 12], [0, 1], { ...clampOpt, easing: SETTLE_EASE });
          const dx = (c.px - c.x) * (1 - diveT);
          const dy = (c.py - c.y) * (1 - diveT);
          const rotFlight = c.protZ * (1 - diveT);
          const arc = Math.sin(diveT * Math.PI) * 70;
          const zDive = interpolate(diveT, [0, 1], [c.pz, HOVER_H]) + arc;
          const z = frame < cue ? c.pz : zDive * (1 - settleT);
          const dealScale = 1 + Math.sin(diveT * Math.PI) * 0.06;
          const press = interpolate(frame, [cue + 10, cue + 11, cue + 12], [1, 0.996, 1], clampOpt);
          const scale = dealScale * press;
          const isLanded = frame >= cue + 12;
          const inPile = frame < cue;
          const antDy = inPile ? ANTICIPATE.pileDown * antT * (frame < ANTICIPATE.to + 2 ? 1 : 0) : 0;
          const antPull = i === 0 && inPile ? ANTICIPATE.topPull * antT : 0;
          const transform = isLanded
            ? 'translate3d(0px, 0px, 0px)'
            : inPile
              ? `translate3d(${c.px - c.x - antPull}px, ${c.py - c.y + antDy}px, ${c.pz}px) rotateZ(${c.protZ}deg)`
              : `translate3d(${dx}px, ${dy}px, ${z}px) rotateZ(${rotFlight}deg) scale(${scale})`;
          const shadowLag = interpolate(frame, [cue + 8, cue + 15], [0, 1], { ...clampOpt, easing: EASE.out });
          const shadow = isLanded
            ? `0 ${(1 + 8 * (1 - shadowLag)).toFixed(1)}px ${(4 + 18 * (1 - shadowLag)).toFixed(1)}px rgba(4,2,12,${(0.25 + 0.2 * (1 - shadowLag)).toFixed(3)})`
            : inPile
              ? i === N - 1 ? '0 1px 3px rgba(0,0,0,.5), 0 18px 40px rgba(0,0,0,0.75)' : '0 1px 2px rgba(0,0,0,.45)'
              : `0 ${22 - 14 * settleT}px ${44 - 30 * settleT}px rgba(0,0,0,${(0.5 - 0.25 * settleT).toFixed(3)})`;
          const showGhost = diveT > 0.02 && diveT < 0.98;
          const gx = (c.px - c.x) * 0.06;
          const gy = (c.py - c.y) * 0.06;
          const pileShade = inPile ? 0.1 * (1 - lightUp) : 0;
          return (
            <div key={c.file} style={{ transformStyle: 'preserve-3d' }}>
              {showGhost ? (
                <div
                  style={{
                    position: 'absolute', left: c.x, top: c.y, width: c.w, height: c.h,
                    transform: `translate3d(${dx + gx}px, ${dy + gy}px, ${z}px) rotateZ(${rotFlight}deg) scale(${scale})`,
                    opacity: 0.28 * (1 - diveT), filter: 'blur(5px)', borderRadius: 12, overflow: 'hidden',
                  }}
                >
                  <Img src={staticFile(`textures/${c.file}`)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
                </div>
              ) : null}
              <div style={{ position: 'absolute', left: c.x, top: c.y, width: c.w, height: c.h, transform, boxShadow: shadow, borderRadius: 12, overflow: 'hidden' }}>
                <Img src={staticFile(`textures/${c.file}`)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
                {pileShade > 0.005 && <div style={{ position: 'absolute', inset: 0, background: `rgba(8,4,20,${pileShade.toFixed(3)})` }} />}
              </div>
            </div>
          );
        })}
      </CamSpace>

      <AbsoluteFill style={{ pointerEvents: 'none', background: 'radial-gradient(ellipse 85% 70% at 50% 42%, transparent 50%, rgba(5,2,14,0.6) 100%)' }} />

      {/* счётчик: тикает вместе с посадками плиток */}
      <MonoTag
        style={{
          position: 'absolute', left: 70, top: 1236, opacity: statIn, display: 'flex', alignItems: 'center', gap: 16,
          transform: `translateY(${((1 - statIn) * 16).toFixed(2)}px)`, textShadow: '0 2px 12px rgba(0,0,0,0.8)',
        }}
      >
        <span style={{ width: 16, height: 16, borderRadius: '50%', background: C.ok, boxShadow: `0 0 ${frame > LAST_LAND ? 18 : 8}px ${C.ok}` }} />
        <span style={{ fontVariantNumeric: 'tabular-nums', color: C.ok }}>{String(landed).padStart(2, '0')}</span>
        <span style={{ color: C.text2 }}>/ {String(N).padStart(2, '0')} нод в сети</span>
      </MonoTag>
      <Grain opacity={0.06} blend="soft-light" />
    </AbsoluteFill>
  );
};
