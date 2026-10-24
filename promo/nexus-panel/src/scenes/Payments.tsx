// Платежи: list-stack-press (video-shotcraft, demos/ui-entrance/list-stack-press).
// Строки платежей одна за другой вылетают снизу и садятся в таблицу; каждая
// новая придавливает уже лежащие (6 px, 8f — «у стопки есть вес»), счётчик
// продлений перекатывается на деление с каждой посадкой, в конце — один блик.
//
// Из исходника: 12f между посадками, полёт 22f bezier(0.45,0.05,0.25,1.12),
// наклон ±2° → 0, масштаб 1.06 → 1, подход снизу 600 px экрана, одометр с
// непрерывной позицией (8f на деление), блик только в скруглениях строк (Q4),
// камера — одна непрерывная кривая, фронтально (Q6).
import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import layout from '../layout.json';
import { PageCam } from '../lib/Cam';
import { Grain, bezier, velocity } from '../lib/Polish';
import { C, FONT, MONO, clampOpt } from '../theme';

export const PAYMENTS_DURATION = 114;

export const PAYMENTS_DEFAULTS = { label: 'продлено автоматически' };

const PAGE_W = layout.width;
const PAGE_H = layout.payments.pageH;
const ROWS = layout.payments.rows.slice(0, 6);
const CUES = [8, 20, 32, 44, 56, 68];
const DUR = 22;
const FLY_EASE = Easing.bezier(0.45, 0.05, 0.25, 1.12);
const TILTS = [2, -2, 2, -2, 2, -2];
const ROLL_DUR = 8;
const ROLL_EASE = Easing.bezier(0.25, 0.8, 0.25, 1);
const LAST = CUES[CUES.length - 1] + DUR;

// камера: от шапки страницы к стопке, одна кривая без остановок в ключах
const CAM_END = LAST + 4;
const CY_EASE = bezier(0.42, 0, 0.2, 1);
const Z_EASE = bezier(0.3, 0, 0.18, 1);
const camAt = (f: number) => {
  const u = Math.min(1, Math.max(0, f / CAM_END));
  return { cx: PAGE_W / 2, cy: 600 + (1000 - 600) * CY_EASE(u), zoom: 2.25 + (2.0 - 2.25) * Z_EASE(u), rotX: 0, rotY: 0, rotZ: 0, persp: 1400 };
};

const flyT = (i: number, f: number) => interpolate(f, [CUES[i], CUES[i] + DUR], [0, 1], { ...clampOpt, easing: FLY_EASE });
const flyY = (i: number, f: number, zoom: number) => (600 / zoom) * (1 - flyT(i, f));
const rollAt = (f: number) => CUES.reduce((pos, c) => pos + interpolate(f, [c + DUR, c + DUR + ROLL_DUR], [0, 1], { ...clampOpt, easing: ROLL_EASE }), 0);

const DIGITS = '0123456789';

export const Payments: React.FC<Partial<typeof PAYMENTS_DEFAULTS>> = (props) => {
  const { label } = { ...PAYMENTS_DEFAULTS, ...props };
  const frame = useCurrentFrame();
  const cam = camAt(frame);
  const rollPos = rollAt(frame);
  const rollV = Math.abs(velocity(rollAt, frame));
  const antT = interpolate(frame, [0, 6], [0, 1], { ...clampOpt, easing: Easing.out(Easing.quad) });

  // следующая строка придавливает уже лежащие
  const stackPress = (settled: number) => {
    let press = 0;
    for (let j = settled + 1; j < CUES.length; j++) {
      const cue = CUES[j] + DUR - 4;
      press = Math.max(press, interpolate(frame, [cue, cue + 4, cue + 8], [0, 3, 0], { ...clampOpt, easing: Easing.inOut(Easing.sin) }));
    }
    return press;
  };

  const glazeX = interpolate(frame, [LAST + 2, LAST + 15], [-300, 900], { ...clampOpt, easing: Easing.bezier(0.45, 0, 0.35, 1) });
  const glazeVis = interpolate(frame, [LAST + 2, LAST + 5, LAST + 12, LAST + 15], [0, 1, 1, 0], clampOpt);

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <PageCam src="textures/payments-empty.png" pageW={PAGE_W} pageH={PAGE_H} cam={cam}>
        {ROWS.map((r, i) => {
          if (frame < CUES[i]) return null;
          const t = flyT(i, frame);
          const y = flyY(i, frame, cam.zoom);
          const vy = velocity((f) => flyY(i, f, cam.zoom), frame);
          const landedT = frame >= CUES[i] + DUR;
          const press = landedT ? stackPress(i) : 0;
          const tilt = TILTS[i] * (1 - Math.min(1, t));
          const scale = 1.06 - 0.06 * Math.min(1, t);
          const air = 1 - Math.min(1, t);
          return (
            <div
              key={r.file}
              style={{
                position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, borderRadius: 8, overflow: 'hidden',
                transform: `translateY(${(y + press).toFixed(2)}px) rotate(${tilt.toFixed(3)}deg) scale(${scale.toFixed(4)})`,
                opacity: Math.min(1, t * 4),
                boxShadow: `0 ${(2 + 16 * air).toFixed(1)}px ${(6 + 30 * air).toFixed(1)}px rgba(4,2,12,${(0.3 + 0.25 * air).toFixed(3)})`,
                filter: Math.abs(vy) > 3 ? `blur(${Math.min(3, Math.abs(vy) * 0.05).toFixed(2)}px)` : undefined,
              }}
            >
              <Img src={staticFile(`textures/${r.file}`)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
              {glazeVis > 0.01 ? (
                <div
                  style={{
                    position: 'absolute', top: -40, bottom: -40, left: glazeX - r.x - (r.y - ROWS[0].y) * 0.35, width: 120, opacity: glazeVis * 0.5,
                    background: 'linear-gradient(90deg, rgba(240,200,255,0) 0%, rgba(250,230,255,0.55) 50%, rgba(240,200,255,0) 100%)', transform: 'skewX(-18deg)',
                  }}
                />
              ) : null}
            </div>
          );
        })}
      </PageCam>

      {/* одометр продлений — экранное пространство, вверху кадра */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 520, background: 'linear-gradient(180deg, rgba(11,8,32,0.9) 0%, rgba(11,8,32,0.7) 55%, rgba(11,8,32,0) 100%)', opacity: antT }} />
      <div style={{ position: 'absolute', left: 70, top: 220, opacity: 0.3 + 0.7 * antT, transform: `scale(${(0.96 + 0.04 * antT).toFixed(4)})`, transformOrigin: '0 50%', fontFamily: FONT, color: C.text }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', fontSize: 150, fontWeight: 900, letterSpacing: '-0.05em', lineHeight: 1, color: C.ok, textShadow: '0 0 40px rgba(110,231,183,0.35)' }}>
          <span>+</span>
          <span style={{ display: 'inline-flex', overflow: 'hidden', height: 150 }}>
            <span style={{ display: 'block', transform: `translateY(${(-rollPos * 150).toFixed(2)}px)`, filter: rollV > 0.03 ? `blur(${Math.min(4, rollV * 18).toFixed(2)}px)` : undefined }}>
              {DIGITS.split('').map((d) => (
                <span key={d} style={{ display: 'block', height: 150, lineHeight: '150px', fontVariantNumeric: 'tabular-nums' }}>{d}</span>
              ))}
            </span>
          </span>
        </div>
        <div style={{ fontFamily: MONO, fontSize: 34, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: C.text2, marginTop: 10 }}>{label}</div>
      </div>
      <Grain opacity={0.05} blend="soft-light" />
    </AbsoluteFill>
  );
};
