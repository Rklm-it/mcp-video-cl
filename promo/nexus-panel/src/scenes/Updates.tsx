// Фишка 04 — все ноды обновляются одной кнопкой.
// Четыре настоящих состояния страницы «Обновления» (заглушка отдаёт ход по
// шагам: очередь → обновляется → снова в сети → готово) сменяют друг друга
// мягкими наплывами — полоски растут, галочки «готово» загораются у каждой ноды.
// Курсор жмёт «Обновить все ноды»; камера держит кнопку и список (Q6 — фронтально).
import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import layout from '../layout.json';
import { CamKey, PageCam, camAt } from '../lib/Cam';
import { Grain } from '../lib/Polish';
import { Pointer } from '../lib/ui';
import { C, clampOpt } from '../theme';

export const UPDATES_DURATION = 140;

const PAGE_W = layout.width;
const PAGE_H = layout.updates.pageH;
const BTN = layout.updates.button;
const CLICK = 22;
// кадр смены состояния → файл; наплыв 6 кадров
const STEPS = [
  { at: CLICK + 2, src: 'textures/upd-1.png' },
  { at: 50, src: 'textures/upd-2.png' },
  { at: 76, src: 'textures/upd-3.png' },
  { at: 102, src: 'textures/upd-4.png' },
];
const XFADE = 6;

const CAM_KEYS: CamKey[] = [
  { frame: 0, cx: PAGE_W / 2, cy: 760, zoom: 1.66 },
  { frame: UPDATES_DURATION, cx: PAGE_W / 2, cy: 780, zoom: 1.6 },
];

export const Updates: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = camAt(CAM_KEYS, frame);
  const target = { x: BTN.x + BTN.w / 2, y: BTN.y + BTN.h / 2 };
  const from = { x: 430, y: 980 };
  const t = interpolate(frame, [6, CLICK - 1], [0, 1], { ...clampOpt, easing: Easing.bezier(0.45, 0, 0.2, 1) });
  const ptr = { x: from.x + (target.x - from.x) * t, y: from.y + (target.y - from.y) * t };
  const ptrO = interpolate(frame, [2, 8, CLICK + 6, CLICK + 12], [0, 1, 1, 0], clampOpt);
  const press = interpolate(frame, [CLICK - 1, CLICK + 1, CLICK + 5], [1, 0.86, 1], clampOpt);
  const glow = interpolate(frame, [CLICK, CLICK + 3, CLICK + 14], [0, 1, 0], clampOpt);

  return (
    <AbsoluteFill style={{ background: `linear-gradient(160deg, ${C.bg} 0%, ${C.bg2} 55%, #0f0828 100%)` }}>
      <PageCam src="textures/upd-0.png" pageW={PAGE_W} pageH={PAGE_H} cam={cam} windowed>
        {STEPS.map((s) => {
          const o = interpolate(frame, [s.at, s.at + XFADE], [0, 1], { ...clampOpt, easing: Easing.inOut(Easing.quad) });
          if (o <= 0) return null;
          return <Img key={s.src} src={staticFile(s.src)} style={{ position: 'absolute', left: 0, top: 0, width: PAGE_W, height: PAGE_H, borderRadius: 14, opacity: o }} />;
        })}
        {glow > 0.01 ? (
          <div style={{ position: 'absolute', left: BTN.x - 2, top: BTN.y - 2, width: BTN.w + 4, height: BTN.h + 4, borderRadius: 12, boxShadow: `0 0 0 2px rgba(240,171,252,${glow.toFixed(3)}), 0 0 22px rgba(232,121,249,${(0.7 * glow).toFixed(3)})` }} />
        ) : null}
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
