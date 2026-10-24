// Фишка 03 — Центр состояния и ИИ-разбор.
// Настоящий «Центр состояния»: рамка-прицел (scan-bracket-sweep) проходит по
// находкам «что сломано и что делать», курсор открывает вкладку «ИИ-разбор»
// и жмёт «Разобрать состояние», камера наезжает на ответ, и он пишется
// строка за строкой (document-typewriter-reveal): маска едет вправо, впереди
// — один «кончик пера» (Q: курсор пишущего всегда один).
import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import layout from '../layout.json';
import { CamKey, PageCam, camAt } from '../lib/Cam';
import { EASE, Grain, ramp } from '../lib/Polish';
import { Pointer } from '../lib/ui';
import { C, clampOpt } from '../theme';

export const STATE_AI_DURATION = 180;

const PAGE_W = layout.width;
const PAGE_H = layout.state.pageH;
const S = layout.state;
const LINES = S.ai.lines;
const TAB = { x: S.aiTab.x + S.aiTab.w / 2, y: S.aiTab.y + S.aiTab.h / 2 };
const BTN = { x: S.analyzeBtn.x + S.analyzeBtn.w / 2, y: S.analyzeBtn.y + S.analyzeBtn.h / 2 };
const TAB_CLICK = 62;
const BTN_CLICK = 80;
const WRITE0 = 92;
const WIPE = 9;
const lineCue = (g: number) => WRITE0 + g * 4.6;
const WRITE_EASE = Easing.bezier(0.4, 0, 0.6, 1);
const boxCy = S.ai.box.y + S.ai.box.h / 2;

const CAM_KEYS: CamKey[] = [
  { frame: 0, cx: PAGE_W / 2, cy: 1000, zoom: 2 },
  { frame: 44, cx: PAGE_W / 2, cy: 1010, zoom: 2 },
  { frame: 56, cx: PAGE_W / 2, cy: 840, zoom: 2 },
  { frame: BTN_CLICK + 2, cx: PAGE_W / 2, cy: 860, zoom: 2 },
  { frame: WRITE0 + 4, cx: PAGE_W / 2, cy: boxCy - 20, zoom: 2.18 },
  { frame: STATE_AI_DURATION, cx: PAGE_W / 2, cy: boxCy - 20, zoom: 2.22 },
];

// рамка-прицел: от первой находки ко второй
const F = S.findings;
const bracketAt = (f: number) => {
  const t = interpolate(f, [26, 40], [0, 1], { ...clampOpt, easing: EASE.smooth });
  const a = F[0], b = F[1] ?? F[0];
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, w: a.w + (b.w - a.w) * t, h: a.h + (b.h - a.h) * t };
};

const pointerAt = (f: number) => {
  const from = { x: 420, y: 1120 };
  const t1 = interpolate(f, [46, TAB_CLICK - 1], [0, 1], { ...clampOpt, easing: Easing.bezier(0.45, 0, 0.2, 1) });
  const t2 = interpolate(f, [TAB_CLICK + 4, BTN_CLICK - 1], [0, 1], { ...clampOpt, easing: Easing.bezier(0.45, 0, 0.2, 1) });
  const p1 = { x: from.x + (TAB.x - from.x) * t1, y: from.y + (TAB.y - from.y) * t1 };
  return { x: p1.x + (BTN.x - p1.x) * t2, y: p1.y + (BTN.y - p1.y) * t2 };
};

export const StateAi: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = camAt(CAM_KEYS, frame);
  const aiOn = interpolate(frame, [TAB_CLICK + 1, TAB_CLICK + 5], [0, 1], clampOpt);
  const ptr = pointerAt(frame);
  const ptrO = interpolate(frame, [42, 48, BTN_CLICK + 4, BTN_CLICK + 10], [0, 1, 1, 0], clampOpt);
  const press = Math.min(
    interpolate(frame, [TAB_CLICK - 1, TAB_CLICK + 1, TAB_CLICK + 5], [1, 0.86, 1], clampOpt),
    interpolate(frame, [BTN_CLICK - 1, BTN_CLICK + 1, BTN_CLICK + 5], [1, 0.86, 1], clampOpt),
  );
  const br = bracketAt(frame);
  const brO = interpolate(frame, [6, 12, 48, 56], [0, 1, 1, 0], clampOpt);
  const brIn = ramp(frame, 6, 10, EASE.snappy);
  const current = LINES.findIndex((_, g) => frame < lineCue(g) + WIPE);

  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <PageCam src="textures/state-full.png" pageW={PAGE_W} pageH={PAGE_H} cam={cam}>
        <Img src={staticFile('textures/ai-empty.png')} style={{ position: 'absolute', left: 0, top: 0, width: PAGE_W, height: PAGE_H, opacity: aiOn }} />

        {/* рамка-прицел по находкам */}
        {brO > 0.01 ? (
          <div style={{ position: 'absolute', left: br.x - 6, top: br.y - 6, width: br.w + 12, height: br.h + 12, opacity: brO, transform: `scale(${(1.08 - 0.08 * brIn).toFixed(4)})` }}>
            {[[0, 0], [1, 0], [0, 1], [1, 1]].map(([rx, ry], k) => (
              <div
                key={k}
                style={{
                  position: 'absolute', width: 22, height: 22, left: rx ? undefined : 0, right: rx ? 0 : undefined, top: ry ? undefined : 0, bottom: ry ? 0 : undefined,
                  borderLeft: rx ? undefined : `2.5px solid ${C.pink}`, borderRight: rx ? `2.5px solid ${C.pink}` : undefined,
                  borderTop: ry ? undefined : `2.5px solid ${C.pink}`, borderBottom: ry ? `2.5px solid ${C.pink}` : undefined,
                  filter: `drop-shadow(0 0 4px ${C.logo})`,
                }}
              />
            ))}
          </div>
        ) : null}

        {/* ответ ИИ пишется строками */}
        {frame >= WRITE0 && LINES.map((l, g) => {
          const t = interpolate(frame, [lineCue(g), lineCue(g) + WIPE], [0, 1], { ...clampOpt, easing: WRITE_EASE });
          if (t <= 0) return null;
          const w = (l.w + 4) * t;
          return (
            <React.Fragment key={g}>
              <div style={{ position: 'absolute', left: l.x - 2, top: l.y - 1, width: w, height: l.h + 3, overflow: 'hidden' }}>
                <Img src={staticFile('textures/ai-full.png')} style={{ position: 'absolute', left: -(l.x - 2), top: -(l.y - 1), width: PAGE_W, height: PAGE_H, maxWidth: 'none' }} />
              </div>
              {g === current && t < 1 ? (
                <div style={{ position: 'absolute', left: l.x - 2 + w, top: l.y, width: 1.6, height: l.h, background: C.pink, boxShadow: `0 0 6px ${C.logo}` }} />
              ) : null}
            </React.Fragment>
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
