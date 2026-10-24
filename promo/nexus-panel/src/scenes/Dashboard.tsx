// Дашборд: spotlight-hero-card (video-shotcraft, demos/opening/spotlight-hero-card).
// Свет гаснет, прожектор ищет по странице, ловит карточку «Выручка 30д», камера
// уходит в косой ракурс слева, карточка взлетает, луч дважды обегает контур,
// и карточка садится обратно — вместе с подписью в той же 3D-сцене.
//
// Тайминги, кривые, глубина темноты, два круга луча — из исходника карточки
// (172f). Переделано: вертикальный кадр, мобильная страница, свет холодный
// сиреневый вместо вольфрама, подпись ПОД карточкой (в вертикали слева места нет).
import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import layout from '../layout.json';
import { CamKey, CamSpace, PageCam, camAt } from '../lib/Cam';
import { EASE, Grain, ramp } from '../lib/Polish';
import { Dust } from '../lib/ui';
import { C, FONT, H, LAMP, W, clampOpt } from '../theme';

export const DASHBOARD_DURATION = 172;

export const DASHBOARD_DEFAULTS = {
  note1: 'Сколько заработал —',
  note2: 'видно сразу',
};

const PAGE_W = layout.width;
const PAGE_H = layout.dashboard.pageH;
const CARD = layout.dashboard.revenue;
const MCX = CARD.x + CARD.w / 2;
const MCY = CARD.y + CARD.h / 2;
const RADIUS = 12;
const BEAM = C.pink;
const BEAM_CORE = 'rgba(255,250,255,0.98)';
const PATCH = 'rgb(40,24,74)';

// — такт (как в исходнике) —
const LOCK = 34;
const PUSH0 = 40;
const PUSH1 = 58;
const RISE0 = 56;
const RISE1 = 66;
const RESEAT0 = 124;
const LAND = 142;

// после наезда карточка в верхней трети кадра, под ней — подпись
const FOCUS = { cx: MCX + 22, cy: MCY + 88 };
const CAM_KEYS: CamKey[] = [
  { frame: 0, cx: PAGE_W / 2, cy: 470, zoom: 2, rotX: 0, rotY: 0, rotZ: 0, persp: 1200 },
  { frame: PUSH0, cx: PAGE_W / 2, cy: 470, zoom: 2, rotX: 0, rotY: 0, rotZ: 0, persp: 1200 },
  { frame: PUSH1, ...FOCUS, zoom: 3.55, rotX: 8, rotY: 28, rotZ: 2, persp: 1200 },
  { frame: DASHBOARD_DURATION, ...FOCUS, zoom: 3.55, rotX: 8, rotY: 28, rotZ: 2, persp: 1200 },
];
const PUSH_EASE = Easing.bezier(0.35, 0, 0.2, 1);
const POP_EASE = Easing.bezier(0.2, 1.25, 0.3, 1);
const RESEAT_EASE = Easing.bezier(0.4, 0, 0.3, 1.05);

// где на экране центр карточки при общем плане (zoom 2) — туда прожектор садится в LOCK
const lockX = ((W / 2 + (MCX - PAGE_W / 2) * 2) / W) * 100;
const lockY = ((H / 2 + (MCY - 470) * 2) / H) * 100;
const afterX = ((W / 2 - 22 * 3.55) / W) * 100;
const afterY = ((H / 2 - 88 * 3.55) / H) * 100;

export const Dashboard: React.FC<Partial<typeof DASHBOARD_DEFAULTS>> = (props) => {
  const { note1, note2 } = { ...DASHBOARD_DEFAULTS, ...props };
  const frame = useCurrentFrame();
  const cam = camAt(CAM_KEYS, frame, PUSH_EASE);

  // включение света: вспыхнул → откат → встал (рубильник)
  const lamp = interpolate(frame, [1, 3, 4, 6], [0, 1, 0.62, 1], clampOpt);

  // прожектор ищет: 3 остановки, затем ловит карточку
  const ST = [4, 10, 13, 19, 22, 28, LOCK, PUSH1];
  const spotX = interpolate(frame, ST, [30, 30, 72, 72, 40, 40, lockX, afterX], { ...clampOpt, easing: EASE.smooth });
  const spotY = interpolate(frame, ST, [52, 52, 34, 34, 64, 64, lockY, afterY], { ...clampOpt, easing: EASE.smooth });
  const poolBase = interpolate(frame, [22, LOCK, PUSH1], [420, 300, 560], { ...clampOpt, easing: EASE.swift });
  const pulse = interpolate(frame, [LOCK, LOCK + 4, LOCK + 10], [0, 0.06, 0], clampOpt);
  const breathe = 1 + 0.015 * Math.sin((frame - LAND) / 14) * ramp(frame, LAND, 20, EASE.out);
  const poolRx = poolBase * (1 + pulse) * breathe;
  const poolRy = poolBase * interpolate(frame, [PUSH0, PUSH1], [0.8, 0.92], clampOpt) * (1 + pulse) * breathe;
  const dark = interpolate(frame, [0, LOCK, PUSH1], [0.9, 0.92, 0.94], clampOpt);
  // после захвата круглое пятно сменяется светом по форме карточки (в пространстве страницы)
  const cardLight = ramp(frame, LOCK + 4, PUSH1 - LOCK - 4, EASE.smooth);
  const holdBreath = 1 + 0.012 * Math.sin((frame - LAND) / 14) * ramp(frame, LAND, 20, EASE.out);

  // карточка: взлёт → парение → посадка
  const rise = interpolate(frame, [RISE0, RISE1], [0, 1], { ...clampOpt, easing: POP_EASE });
  const reseat = interpolate(frame, [RESEAT0, LAND], [0, 1], { ...clampOpt, easing: RESEAT_EASE });
  const lift = rise * (1 - reseat);
  const bob = Math.sin(((frame - RISE1) / 40) * Math.PI * 2) * 4 * lift;
  const z = 52 * lift + bob;
  const landed = frame >= LAND;
  const press = interpolate(frame, [LAND - 4, LAND - 1, LAND], [1, 0.997, 1], clampOpt);
  const shadow = `${-7 * lift}px ${7 * lift}px ${10 + 10 * lift}px rgba(6,2,16,${0.4 * lift}), ${-24 * lift}px ${32 * lift}px ${60 * lift}px rgba(6,2,16,${0.5 * lift})`;

  const slotVis = Math.min(1, rise * 2) * (1 - reseat);
  const landPulse = interpolate(frame, [LAND - 4, LAND, LAND + 14], [0, 1, 0], clampOpt);
  const slotEdge = Math.min(1, 0.45 * (1 - reseat)) + landPulse * 0.5;

  // луч по контуру: первый круг быстрый и яркий, второй медленный и слабый
  const beam1Prog = interpolate(frame, [68, 82], [0, 1], clampOpt);
  const beam1On = frame >= 67 && frame <= 83;
  const beam2Prog = interpolate(frame, [88, 108], [0, 1], { ...clampOpt, easing: EASE.swift });
  const beam2On = frame >= 87 && frame <= 109;
  const beamTrail = interpolate(frame, [108, 122], [0.4, 0], clampOpt);
  const bw = CARD.w + 4;
  const bh = CARD.h + 4;

  const hiresIn = interpolate(frame, [PUSH0, PUSH0 + 6], [0, 1], clampOpt);

  // подпись
  const noteIn = ramp(frame, 70, 14, EASE.out);
  const noteSettle = interpolate(frame, [RESEAT0 - 4, LAND], [0, 1], { ...clampOpt, easing: RESEAT_EASE });
  const noteZ = 3 + (56 + Math.sin(((frame - 70) / 44) * Math.PI * 2) * 2) * (1 - noteSettle);
  const hl = ramp(frame, 84, 12, EASE.swift);

  // объёмный луч света сверху справа
  const px = (spotX / 100) * W;
  const py = (spotY / 100) * H;
  const sx = px + 360;
  const sy = -900;
  const coneW = poolRx * 0.6;
  const cone = `${sx - 22}px ${sy}px, ${sx + 22}px ${sy}px, ${px + coneW}px ${py}px, ${px - coneW}px ${py}px`;

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <PageCam src="textures/dashboard-full.png" pageW={PAGE_W} pageH={PAGE_H} cam={cam}>
        {/* тёмный слой страницы с мягким вырезом по форме карточки */}
        {cardLight > 0.001 ? (
          <svg width={PAGE_W} height={PAGE_H} style={{ position: 'absolute', left: 0, top: 0, transform: 'translateZ(1px)', opacity: cardLight }}>
            <defs>
              <filter id="dash-tight" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9" /></filter>
              <filter id="dash-wide" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="26" /></filter>
              <mask id="dash-hole" maskUnits="userSpaceOnUse" x={0} y={0} width={PAGE_W} height={PAGE_H}>
                <rect x={0} y={0} width={PAGE_W} height={PAGE_H} fill="white" />
                <rect x={CARD.x - 26} y={CARD.y - 22} width={CARD.w + 52} height={CARD.h + 44} rx={30} fill="#262626" filter="url(#dash-wide)" />
                <rect x={CARD.x - 6} y={CARD.y - 6} width={CARD.w + 12} height={CARD.h + 12} rx={RADIUS + 6} fill="black" filter="url(#dash-tight)" />
              </mask>
            </defs>
            <rect x={0} y={0} width={PAGE_W} height={PAGE_H} fill="rgb(8,4,20)" fillOpacity={Math.min(0.97, 0.94 * holdBreath)} mask="url(#dash-hole)" />
          </svg>
        ) : null}

        <div style={{ transformStyle: 'preserve-3d' }}>
          {slotVis > 0.02 || landPulse > 0.02 ? (
            <div
              style={{
                position: 'absolute', left: CARD.x - 1, top: CARD.y - 1, width: CARD.w + 2, height: CARD.h + 2, transform: 'translateZ(1.5px)',
                background: slotVis > 0.02 ? PATCH : 'transparent', borderRadius: RADIUS, opacity: Math.max(slotVis, landPulse),
                boxShadow: `inset 0 0 14px rgba(240,171,252,${(0.16 * slotEdge).toFixed(3)})`,
              }}
            >
              <div style={{ position: 'absolute', inset: 0, borderRadius: RADIUS, border: `1px solid ${BEAM}`, opacity: slotEdge, boxShadow: landPulse > 0.02 ? `0 0 ${(14 * landPulse).toFixed(1)}px rgba(240,171,252,0.8)` : undefined }} />
            </div>
          ) : null}

          <div
            style={{
              position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h,
              transform: `translateZ(${(z + 2).toFixed(2)}px) scale(${press})`, transformOrigin: 'center center', transformStyle: 'preserve-3d',
            }}
          >
            <div style={{ position: 'absolute', inset: 0, borderRadius: RADIUS, overflow: 'hidden', boxShadow: landed ? 'none' : shadow }}>
              <Img src={staticFile('textures/dash-revenue.png')} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
              <Img src={staticFile('textures/dash-revenue-hires.png')} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: hiresIn }} />
              <div style={{ position: 'absolute', inset: 0, background: `linear-gradient(200deg, rgba(${LAMP},0.22), rgba(${LAMP},0) 45%, rgba(10,4,20,0.1) 100%)`, opacity: lift }} />
            </div>
            <div style={{ position: 'absolute', inset: 0, borderRadius: RADIUS, boxShadow: `inset 0 0 0 0.6px rgba(255,255,255,${(0.7 * lift).toFixed(3)}), 0 0 0 1px rgba(240,200,255,${(0.6 * cardLight).toFixed(3)}), 0 0 26px rgba(232,121,249,${(0.22 * cardLight).toFixed(3)})` }} />

            {(beam1On || beam2On) && lift > 0.4 ? (
              <svg width={bw} height={bh} viewBox={`0 0 ${bw} ${bh}`} style={{ position: 'absolute', left: -2, top: -2, overflow: 'visible', opacity: beam1On ? 1 : 0.62, filter: 'drop-shadow(0 0 3px rgba(240,171,252,0.95)) drop-shadow(0 0 9px rgba(250,220,255,0.6))' }}>
                <rect x={1} y={1} width={bw - 2} height={bh - 2} rx={RADIUS} fill="none" stroke={BEAM} strokeWidth={beam1On ? 2.6 : 1.8} strokeLinecap="round" pathLength={1} strokeDasharray="0.16 1" strokeDashoffset={-(beam1On ? beam1Prog : beam2Prog)} />
                <rect x={1} y={1} width={bw - 2} height={bh - 2} rx={RADIUS} fill="none" stroke={BEAM_CORE} strokeWidth={beam1On ? 1.3 : 0.9} strokeLinecap="round" pathLength={1} strokeDasharray="0.16 1" strokeDashoffset={-(beam1On ? beam1Prog : beam2Prog)} />
              </svg>
            ) : null}
            {beamTrail > 0.01 ? <div style={{ position: 'absolute', inset: -2, borderRadius: RADIUS + 2, border: `1px solid ${BEAM}`, opacity: beamTrail }} /> : null}
          </div>
        </div>
      </PageCam>

      {/* свет в экранном пространстве: темнота вокруг пятна, само пятно, объёмный луч */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(${(poolRx * 1.35).toFixed(1)}px ${(poolRy * 1.35).toFixed(1)}px at ${spotX}% ${spotY}%, rgba(8,4,20,0) 0%, rgba(8,4,20,0) 26%, rgba(8,4,20,${(dark * 0.25).toFixed(3)}) 44%, rgba(8,4,20,${(dark * 0.62).toFixed(3)}) 62%, rgba(8,4,20,${(dark * 0.9).toFixed(3)}) 80%, rgba(8,4,20,${dark.toFixed(3)}) 100%)`,
          mixBlendMode: 'multiply', opacity: lamp * (1 - cardLight),
        }}
      />
      <AbsoluteFill style={{ background: 'rgb(8,4,20)', mixBlendMode: 'multiply', opacity: 0.84 * (1 - lamp) }} />
      <AbsoluteFill
        style={{
          background: `radial-gradient(${(poolRx * 1.2).toFixed(1)}px ${(poolRy * 1.2).toFixed(1)}px at ${spotX}% ${spotY}%, rgba(${LAMP},0.22) 0%, rgba(${LAMP},0.1) 50%, rgba(${LAMP},0) 80%)`,
          mixBlendMode: 'soft-light', opacity: lamp * (1 - cardLight),
        }}
      />
      <AbsoluteFill style={{ mixBlendMode: 'screen', opacity: lamp * (1 - 0.45 * ramp(frame, PUSH0, 18, EASE.smooth)) }}>
        <div style={{ position: 'absolute', inset: 0, filter: 'blur(28px)' }}>
          <div
            style={{
              position: 'absolute', inset: 0, clipPath: `polygon(${cone})`,
              background: `linear-gradient(${((Math.atan2(py - sy, px - sx) * 180) / Math.PI - 90).toFixed(1)}deg, rgba(${LAMP},0.3) 0%, rgba(${LAMP},0.14) 60%, rgba(${LAMP},0.05) 100%)`,
            }}
          />
        </div>
        <div style={{ position: 'absolute', inset: 0, clipPath: `polygon(${cone})` }}>
          <Dust count={30} seed={4} opacity={0.55} color="#f5e8ff" />
        </div>
      </AbsoluteFill>

      {/* подпись: та же камера, но поверх света — светится сама, не гаснет вместе со страницей */}
      <CamSpace cam={cam} pageW={PAGE_W} pageH={PAGE_H}>
        {frame >= 70 ? (
          <div style={{ transformStyle: 'preserve-3d' }}>
            <div
              style={{
                position: 'absolute', left: CARD.x - 20, top: CARD.y + CARD.h + 8, width: 330, height: 96,
                transform: `translateZ(${(noteZ - 1).toFixed(2)}px) translateY(${((1 - noteIn) * 12).toFixed(2)}px)`,
                background: 'radial-gradient(ellipse 50% 50% at 45% 50%, rgba(10,5,24,0.95) 0%, rgba(10,5,24,0.85) 60%, rgba(10,5,24,0) 100%)',
                filter: 'blur(4px)', opacity: noteIn,
              }}
            />
            <div
              style={{
                position: 'absolute', left: CARD.x + 2, top: CARD.y + CARD.h + 22, width: 'max-content', whiteSpace: 'nowrap',
                transform: `translateZ(${noteZ.toFixed(2)}px) translateY(${((1 - noteIn) * 12).toFixed(2)}px)`,
                opacity: noteIn, filter: noteIn < 1 ? `blur(${((1 - noteIn) * 2).toFixed(2)}px)` : undefined,
                fontFamily: FONT, letterSpacing: '-0.03em', lineHeight: 1.12,
              }}
            >
              <div style={{ fontSize: 24, fontWeight: 800, color: C.text, textShadow: '0 1px 10px rgba(0,0,0,0.6)' }}>{note1}</div>
              <div style={{ position: 'relative', display: 'inline-block', marginTop: 2 }}>
                <div style={{ position: 'absolute', left: -4, top: '8%', bottom: '2%', width: `calc(${hl.toFixed(4)} * (100% + 8px))`, background: C.pink, borderRadius: 3 }} />
                <div style={{ position: 'relative', fontSize: 24, fontWeight: 800, color: hl > 0.55 ? C.ink : C.text }}>{note2}</div>
              </div>
            </div>
          </div>
        ) : null}
      </CamSpace>
      <Grain opacity={0.07} blend="soft-light" />
    </AbsoluteFill>
  );
};
