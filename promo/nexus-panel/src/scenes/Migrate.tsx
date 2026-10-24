// Фишка 05 — переезд с других панелей.
// Часть A — bezier-source-converge-merge (video-shotcraft, demos/ui-entrance/
// bezier-source-converge-merge): четыре панели-источника, линии подключаются
// по очереди (сдвиг ~3 кадра), плашки едут ПО настоящей кривой к Nexus и в
// последней четверти пути «всасываются» (размер падает в 4 раза быстрее),
// значок Nexus отвечает импульсом, линии убираются от начала.
// Часть B — настоящий результат разбора бэкапа: «Опознано: Remnawave»,
// плитки-счётчики въезжают в свои места (row-embed).
// Доли времени из исходника (на 74 кадра части A): линии 0.04+i·0.045 / 0.17,
// путь 0.34→0.74 inOutCubic, импульс 0.70→0.86, стирание 0.78→0.90.
import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import layout from '../layout.json';
import { CamKey, PageCam, camAt } from '../lib/Cam';
import { EASE, Grain, ramp } from '../lib/Polish';
import { C, FONT, clampOpt } from '../theme';

export const MIGRATE_DURATION = 140;

const PAGE_W = layout.width;
const PAGE_H = layout.import.pageH;
const TILES = layout.import.tiles;
const A = 74; // длина части A
const at = (u: number) => u * A;

const SOURCES = ['Remnawave', 'Marzban', '3x-ui', 'Hiddify'];
const ROW_Y = [770, 890, 1010, 1130];
const DWELL_X = 300;
const M = { x: 800, y: 950 };
const cubic = (p0: number, p1: number, p2: number, p3: number, t: number) =>
  (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3;
const curve = (y: number, t: number) => ({
  x: cubic(DWELL_X, DWELL_X + 260, M.x - 260, M.x, t),
  y: cubic(y, y, M.y, M.y, t),
});
const pathD = (y: number) => `M -40 ${y} L ${DWELL_X} ${y} C ${DWELL_X + 260} ${y} ${M.x - 260} ${M.y} ${M.x} ${M.y}`;
const PATH_LEN = (y: number) => DWELL_X + 40 + Math.hypot(M.x - DWELL_X, M.y - y) * 1.15; // хватает для dasharray

const CAM_KEYS: CamKey[] = [
  { frame: A, cx: PAGE_W / 2, cy: 690, zoom: 1.62 },
  { frame: MIGRATE_DURATION, cx: PAGE_W / 2, cy: 652, zoom: 1.7 },
];
const EMBED_EASE = Easing.bezier(0.3, 0, 0.25, 1.15);
const inOutCubic = Easing.bezier(0.65, 0, 0.35, 1);

export const Migrate: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = camAt(CAM_KEYS, frame);
  const conv = interpolate(frame, [at(0.34), at(0.74)], [0, 1], { ...clampOpt, easing: inOutCubic });
  const erase = interpolate(frame, [at(0.78), at(0.9)], [0, 1], { ...clampOpt, easing: Easing.out(Easing.quad) });
  const badgeIn = interpolate(frame, [at(0.16), at(0.26)], [0, 1], { ...clampOpt, easing: EASE.out });
  const pulse = frame < at(0.78)
    ? interpolate(frame, [at(0.7), at(0.78)], [0, 0.12], { ...clampOpt, easing: Easing.out(Easing.back(1.7)) })
    : interpolate(frame, [at(0.78), at(0.86)], [0.12, 0], { ...clampOpt, easing: Easing.out(Easing.quad) });
  // переход к странице: значок раздувается и растворяется
  const toPage = ramp(frame, A - 6, 12, EASE.swift);
  const pk = interpolate(frame, [at(0.1), at(0.74)], [0, 2], clampOpt);

  return (
    <AbsoluteFill style={{ background: `linear-gradient(160deg, ${C.bg} 0%, ${C.bg2} 55%, #0f0828 100%)`, fontFamily: FONT }}>
      {/* часть B: страница с результатом разбора */}
      {frame >= A - 6 ? (
        <AbsoluteFill style={{ opacity: toPage }}>
          <PageCam src="textures/import-after-empty.png" pageW={PAGE_W} pageH={PAGE_H} cam={cam} windowed>
            {TILES.map((tl, i) => {
              const cue = A + 6 + i * 6;
              if (frame < cue) return null;
              const t = interpolate(frame, [cue, cue + 12], [0, 1], { ...clampOpt, easing: EMBED_EASE });
              const air = 1 - Math.min(1, t);
              return (
                <div
                  key={tl.file}
                  style={{
                    position: 'absolute', left: tl.x, top: tl.y, width: tl.w, height: tl.h, borderRadius: 10, overflow: 'hidden', opacity: Math.min(1, t * 3),
                    transform: `translateX(${(-220 * air).toFixed(2)}px) scale(${(1 + 0.04 * air).toFixed(4)})`,
                    boxShadow: `0 ${(2 + 12 * air).toFixed(1)}px ${(6 + 22 * air).toFixed(1)}px rgba(4,2,12,${(0.3 + 0.2 * air).toFixed(3)})`,
                  }}
                >
                  <Img src={staticFile(`textures/${tl.file}`)} style={{ width: '100%', height: '100%', display: 'block' }} />
                </div>
              );
            })}
          </PageCam>
        </AbsoluteFill>
      ) : null}

      {/* часть A: источники сходятся в Nexus */}
      {frame < A + 6 ? (
        <AbsoluteFill style={{ opacity: 1 - toPage }}>
          <svg width={1080} height={1920} style={{ position: 'absolute', inset: 0 }}>
            <defs><linearGradient id="mg" x1="0" x2="1"><stop offset="0" stopColor={C.cyan} /><stop offset="1" stopColor={C.logo} /></linearGradient></defs>
            {ROW_Y.map((y, i) => {
              const len = PATH_LEN(y);
              const draw = interpolate(frame, [at(0.04 + i * 0.045), at(0.04 + i * 0.045 + 0.17)], [0, 1], { ...clampOpt, easing: Easing.out(Easing.quad) });
              const offset = erase > 0 ? -erase * len : len * (1 - draw);
              return <path key={i} d={pathD(y)} fill="none" stroke="url(#mg)" strokeWidth={5} strokeLinecap="round" strokeDasharray={len} strokeDashoffset={offset} opacity={0.85} style={{ filter: 'drop-shadow(0 0 6px rgba(232,121,249,0.5))' }} />;
            })}
            {frame > at(0.1) && frame < at(0.74) && ROW_Y.map((y, i) => {
              const u = (pk + i * 0.13) % 1;
              const p = curve(y, u);
              return <circle key={`p${i}`} cx={p.x} cy={p.y} r={7} fill="#fff" opacity={1 - Math.abs(u - 0.5) * 0.6} style={{ filter: `drop-shadow(0 0 8px ${C.pink})` }} />;
            })}
          </svg>
          {SOURCES.map((name, i) => {
            const y = ROW_Y[i];
            const pos = conv > 0 ? curve(y, conv) : { x: DWELL_X, y };
            const appear = ramp(frame, at(0.04 + i * 0.045), 8, EASE.out);
            const size = conv < 0.75 ? 1 - (conv / 0.75) * 0.66 : 0.34 * (1 - (conv - 0.75) / 0.25);
            const fade = conv > 0.92 ? 1 - (conv - 0.92) / 0.08 : 1;
            return (
              <div
                key={name}
                style={{
                  position: 'absolute', left: pos.x, top: pos.y, transform: `translate(-100%, -50%) scale(${Math.max(0, size).toFixed(4)})`, transformOrigin: '100% 50%',
                  opacity: appear * fade, padding: '14px 26px', borderRadius: 16, background: 'rgba(30,20,60,0.95)', border: '2px solid rgba(192,132,252,0.45)',
                  fontSize: 44, fontWeight: 800, color: C.text, whiteSpace: 'nowrap', boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
                }}
              >
                {name}
              </div>
            );
          })}
          {/* значок Nexus в точке схода */}
          <div
            style={{
              position: 'absolute', left: M.x, top: M.y, transform: `translate(-50%, -50%) scale(${((0.7 + 0.3 * badgeIn) * (1 + pulse) * (1 + 1.2 * toPage)).toFixed(4)})`,
              opacity: badgeIn, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10,
            }}
          >
            <div style={{ width: 150, height: 150, borderRadius: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', background: `linear-gradient(135deg, ${C.logo}, ${C.accentDim})`, boxShadow: `0 0 ${(40 + 160 * pulse).toFixed(1)}px rgba(232,121,249,0.7)`, fontSize: 96, fontWeight: 900, color: '#fff' }}>
              N
            </div>
            <div style={{ fontSize: 44, fontWeight: 900, color: C.text, letterSpacing: '0.04em' }}>NEXUS</div>
          </div>
        </AbsoluteFill>
      ) : null}
      <Grain opacity={0.05} blend="soft-light" />
    </AbsoluteFill>
  );
};
