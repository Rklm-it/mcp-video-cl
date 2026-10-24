// Фишка 02 — маршрутизация по сервисам на ноде.
// Настоящая вкладка «Маршрутизация и DNS» европейской ноды: курсор жмёт чипы
// сервисов (Telegram, YouTube, нейросети — напрямую из Европы; Госуслуги и
// банки — через российскую ноду), камера, как прокрутка, спускается к списку
// правил, и правила одно за другим встают в свои места (row-embed, Q9).
// Щелчки — type-and-filter (двойная рябь, нажатие курсора).
import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import layout from '../layout.json';
import { CamKey, PageCam, camAt } from '../lib/Cam';
import { Grain } from '../lib/Polish';
import { Pointer } from '../lib/ui';
import { C, clampOpt } from '../theme';

export const ROUTING_DURATION = 156;

const PAGE_W = layout.width;
const PAGE_H = layout.routing.pageH;
const CH = layout.routing.chips;
const RULES = layout.routing.rules;

const TAPS = [
  { at: 18, chip: CH.telegram },
  { at: 36, chip: CH.youtube },
  { at: 54, chip: CH.ai },
  { at: 90, chip: CH.gosuslugi },
];
const center = (b: { x: number; y: number; w: number; h: number }) => ({ x: b.x + b.w / 2, y: b.y + b.h / 2 });

const CAM_KEYS: CamKey[] = [
  { frame: 0, cx: PAGE_W / 2, cy: 650, zoom: 1.8 },
  { frame: 60, cx: PAGE_W / 2, cy: 668, zoom: 1.8 },
  { frame: 84, cx: PAGE_W / 2, cy: 1122, zoom: 1.8 },
  { frame: 96, cx: PAGE_W / 2, cy: 1122, zoom: 1.8 },
  { frame: 112, cx: PAGE_W / 2, cy: 1217, zoom: 1.8 },
  { frame: ROUTING_DURATION, cx: PAGE_W / 2, cy: 1220, zoom: 1.81 },
];
const EMBED_EASE = Easing.bezier(0.3, 0, 0.25, 1.15);
const RULE_CUES = [110, 116, 122, 128];

// курсор: от нажатия к нажатию, между ними — плавный перелёт
const pointerAt = (f: number) => {
  const pts = [{ at: 4, p: { x: 420, y: 760 } }, ...TAPS.map((t) => ({ at: t.at, p: center(t.chip) }))];
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    const start = Math.max(a.at + 3, b.at - 12);
    if (f <= b.at) {
      const t = interpolate(f, [start, b.at - 1], [0, 1], { ...clampOpt, easing: Easing.bezier(0.45, 0, 0.2, 1) });
      return { x: a.p.x + (b.p.x - a.p.x) * t, y: a.p.y + (b.p.y - a.p.y) * t };
    }
  }
  return center(TAPS[TAPS.length - 1].chip);
};

export const Routing: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = camAt(CAM_KEYS, frame);
  const ptr = pointerAt(frame);
  const ptrO = interpolate(frame, [2, 8, TAPS[3].at + 6, TAPS[3].at + 12], [0, 1, 1, 0], clampOpt);
  const press = TAPS.reduce((m, t) => Math.min(m, interpolate(frame, [t.at - 1, t.at + 1, t.at + 5], [1, 0.86, 1], clampOpt)), 1);

  return (
    <AbsoluteFill style={{ background: `linear-gradient(160deg, ${C.bg} 0%, ${C.bg2} 55%, #0f0828 100%)` }}>
      <PageCam src="textures/routing-norules.png" pageW={PAGE_W} pageH={PAGE_H} cam={cam} windowed>
        {/* нажатые чипы подсвечиваются и остаются выбранными */}
        {TAPS.map((t, i) => {
          if (frame < t.at) return null;
          const on = interpolate(frame, [t.at, t.at + 4], [0, 1], clampOpt);
          const pulse = interpolate(frame, [t.at, t.at + 3, t.at + 9], [1, 1.12, 1], clampOpt);
          return (
            <div
              key={i}
              style={{
                position: 'absolute', left: t.chip.x - 1, top: t.chip.y - 1, width: t.chip.w + 2, height: t.chip.h + 2, borderRadius: 8,
                transform: `scale(${pulse.toFixed(4)})`, boxShadow: `0 0 0 1.5px rgba(240,171,252,${on.toFixed(3)}), 0 0 12px rgba(232,121,249,${(0.55 * on).toFixed(3)})`,
                background: `rgba(192,132,252,${(0.16 * on).toFixed(3)})`,
              }}
            />
          );
        })}
        {TAPS.flatMap((t, i) => [0, 1].map((k) => {
          const start = t.at + k * 3;
          if (frame < start || frame > start + 10) return null;
          const u = interpolate(frame, [start, start + 10], [0, 1], { ...clampOpt, easing: Easing.out(Easing.cubic) });
          const rad = 5 + (k === 0 ? 20 : 30) * u;
          const c = center(t.chip);
          return <div key={`r${i}${k}`} style={{ position: 'absolute', left: c.x - rad, top: c.y - rad, width: rad * 2, height: rad * 2, borderRadius: '50%', border: `${k === 0 ? 1.2 : 0.9}px solid ${C.pink}`, opacity: 1 - u, boxSizing: 'border-box' }} />;
        }))}

        {/* правила встают в список */}
        {RULES.map((r, i) => {
          const cue = RULE_CUES[i];
          if (frame < cue) return null;
          const t = interpolate(frame, [cue, cue + 12], [0, 1], { ...clampOpt, easing: EMBED_EASE });
          const air = 1 - Math.min(1, t);
          return (
            <div
              key={r.file}
              style={{
                position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, borderRadius: 10, overflow: 'hidden', opacity: Math.min(1, t * 3),
                transform: `translateY(${(-70 * air).toFixed(2)}px) scale(${(1 + 0.05 * air).toFixed(4)})`,
                boxShadow: `0 ${(2 + 14 * air).toFixed(1)}px ${(6 + 26 * air).toFixed(1)}px rgba(4,2,12,${(0.3 + 0.25 * air).toFixed(3)})`,
              }}
            >
              <Img src={staticFile(`textures/${r.file}`)} style={{ width: '100%', height: '100%', display: 'block' }} />
            </div>
          );
        })}

        {ptrO > 0.01 ? (
          <div style={{ position: 'absolute', left: ptr.x, top: ptr.y, opacity: ptrO, transform: `scale(${(press / cam.zoom).toFixed(4)})`, transformOrigin: '0 0' }}>
            <Pointer size={36} />
          </div>
        ) : null}
      </PageCam>
      <Grain opacity={0.05} blend="soft-light" />
    </AbsoluteFill>
  );
};
