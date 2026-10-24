// 2.5D-камера над снимком страницы — PageCam из video-shotcraft (assets/lib/PageCam.tsx),
// переведённая на вертикальный кадр 1080×1920 и мобильную страницу шириной 540 CSS px.
//
// Увеличение идёт CSS-свойством `zoom`, а не transform: scale — Chromium тогда
// растеризует страницу в увеличенном размере и текст остаётся резким (審美 Q2).
// Фокус (cx, cy) в координатах страницы стоит в центре кадра:
//   cx*zoom + Tx*zoom = W/2  ⟹  Tx = W/2/zoom − cx  (и так же по y).
import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, staticFile } from 'remotion';
import { H, W, clampOpt } from '../theme';

export type CamKey = {
  frame: number;
  cx: number;
  cy: number;
  zoom: number;
  rotX?: number;
  rotY?: number;
  rotZ?: number;
  persp?: number;
};
export type Cam = Required<Omit<CamKey, 'frame'>>;

export const CAM_EASE = Easing.bezier(0.33, 0, 0.15, 1);

export const camAt = (keys: CamKey[], frame: number, ease: (t: number) => number = CAM_EASE): Cam => {
  let a = keys[0];
  let b = keys[keys.length - 1];
  for (let i = 0; i < keys.length - 1; i++) {
    if (frame >= keys[i].frame && frame <= keys[i + 1].frame) { a = keys[i]; b = keys[i + 1]; break; }
  }
  if (frame > b.frame) a = b;
  const t = a.frame === b.frame ? 1 : interpolate(frame, [a.frame, b.frame], [0, 1], { ...clampOpt, easing: ease });
  const m = (x: number | undefined, y: number | undefined, d: number) => (x ?? d) + ((y ?? d) - (x ?? d)) * t;
  return {
    cx: m(a.cx, b.cx, 0), cy: m(a.cy, b.cy, 0), zoom: m(a.zoom, b.zoom, 1),
    rotX: m(a.rotX, b.rotX, 0), rotY: m(a.rotY, b.rotY, 0), rotZ: m(a.rotZ, b.rotZ, 0), persp: m(a.persp, b.persp, 1400),
  };
};

/** Слой в пространстве страницы под заданной камерой. Его же используют подписи,
 *  которые должны жить в той же 3D-сцене, но рисоваться поверх света (C3). */
export const CamSpace: React.FC<{ cam: Cam; pageW: number; pageH: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ cam, pageW, pageH, children, style }) => (
  <AbsoluteFill style={{ overflow: 'hidden', pointerEvents: 'none' }}>
    <div style={{ position: 'absolute', inset: 0, perspective: `${(cam.persp * cam.zoom).toFixed(2)}px`, perspectiveOrigin: `${W / 2}px ${H / 2}px` }}>
      <div
        style={{
          position: 'absolute', width: pageW, height: pageH, zoom: cam.zoom,
          transform: `translate(${(W / 2 / cam.zoom - cam.cx).toFixed(3)}px, ${(H / 2 / cam.zoom - cam.cy).toFixed(3)}px) rotateY(${cam.rotY.toFixed(3)}deg) rotateX(${cam.rotX.toFixed(3)}deg) rotateZ(${cam.rotZ.toFixed(3)}deg)`,
          transformOrigin: `${cam.cx.toFixed(2)}px ${cam.cy.toFixed(2)}px`,
          transformStyle: 'preserve-3d',
          ...style,
        }}
      >
        {children}
      </div>
    </div>
  </AbsoluteFill>
);

/** Страница-текстура + дочерние элементы в её координатах.
 *  windowed — страница уже кадра (zoom < 2): рисуем её окном со скруглением, рамкой и тенью. */
export const PageCam: React.FC<{
  src: string;
  pageW: number;
  pageH: number;
  cam: Cam;
  radius?: number;
  windowed?: boolean;
  children?: React.ReactNode;
}> = ({ src, pageW, pageH, cam, radius = 0, windowed = false, children }) => (
  <CamSpace cam={cam} pageW={pageW} pageH={pageH}>
    <Img
      src={staticFile(src)}
      style={{
        position: 'absolute', left: 0, top: 0, width: pageW, height: pageH, borderRadius: windowed ? 14 : radius,
        boxShadow: windowed ? '0 0 0 1px rgba(192,132,252,0.3), 0 30px 90px rgba(0,0,0,0.65), 0 0 70px rgba(168,85,247,0.22)' : undefined,
      }}
    />
    {children}
  </CamSpace>
);
