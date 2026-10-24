// Концовка: outro-group-photo-launch (video-shotcraft, demos/outro/outro-group-photo-launch).
// По одному элементу от каждого показанного раздела (выручка, онлайн, нода,
// клиент, платёж — Q8) слетаются с четырёх сторон и окружают логотип; логотип
// вдавливается по буквам, остальные отступают на второй план, затем —
// контакт и цена. Пик энергии ролика, сверху — держим кадр больше секунды (R1).
//
// Из исходника: вылет каждые 3f с 4-го кадра, полёт 12f bezier(0.34,1.4,0.44,1)
// (настоящий перелёт, y1 > 1), разворот ×2 → итоговый угол в пределах ±5°,
// масштаб ×1.12 → 1, размытие по скорости, «отход назад» −12% непрозрачности,
// буквы логотипа delay = 42 + i·1.8 по 8f, линия и её продолжения, кран
// rotateX 4° → 0 со scale 1.06 → 1, затем медленный наезд, сценический свет и пыль.
import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import layout from '../layout.json';
import { EASE, Grain, SpeedBlur, ramp, velocity } from '../lib/Polish';
import { Dust } from '../lib/ui';
import { C, FONT, MONO, clampOpt } from '../theme';

export const OUTRO_DURATION = 180;

export const OUTRO_DEFAULTS = {
  brand: 'NEXUS',
  eyebrow: 'панель для своего VPN-сервиса',
  contact: '@Nexus_dev',
  contactNote: 'демо и вопросы — в Telegram',
  price: 'от 3 990 ₽ в месяц',
};

const FLY_EASE = Easing.bezier(0.34, 1.4, 0.44, 1);
const CRANE_EASE = Easing.bezier(0.3, 0, 0.2, 1);
const L = layout;

type El = { file: string; w: number; h: number; cx: number; cy: number; scale: number; rot: number; dx: number; dy: number; cue: number };
// порядок отрисовки = порядок вылета: поздние ложатся сверху
const ELS: El[] = [
  { file: 'dash-revenue-hires.png', w: L.dashboard.revenue.w, h: L.dashboard.revenue.h, cx: 300, cy: 330, scale: 1.5, rot: -5, dx: -520, dy: -80, cue: 4 },
  { file: 'dash-online.png', w: L.dashboard.online.w, h: L.dashboard.online.h, cx: 790, cy: 390, scale: 1.35, rot: 4, dx: 520, dy: -60, cue: 7 },
  { file: 'node1.png', w: L.servers.tiles[0].w, h: L.servers.tiles[0].h, cx: 560, cy: 570, scale: 1.2, rot: -2, dx: -560, dy: -220, cue: 10 },
  { file: L.payments.rows[0].file, w: L.payments.rows[0].w, h: L.payments.rows[0].h, cx: 540, cy: 1440, scale: 1.15, rot: 2.5, dx: 560, dy: 260, cue: 13 },
  { file: L.users.rows[L.users.target].file, w: L.users.rows[0].w, h: L.users.rows[0].h, cx: 520, cy: 1590, scale: 1.1, rot: -1.5, dx: 0, dy: 420, cue: 16 },
];
const FLY = 12;

const LETTER_DELAY = (i: number) => 42 + i * 1.8;

export const Outro: React.FC<Partial<typeof OUTRO_DEFAULTS>> = (props) => {
  const { brand, eyebrow, contact, contactNote, price } = { ...OUTRO_DEFAULTS, ...props };
  const frame = useCurrentFrame();
  const letters = brand.split('');

  const crane = ramp(frame, 0, 40, CRANE_EASE);
  const slowPush = ramp(frame, 36, OUTRO_DURATION - 36, EASE.smooth) * 0.035;
  const stageScale = 1.06 - 0.06 * crane + slowPush;
  const stageTilt = 4 * (1 - crane);

  const stepBack = ramp(frame, 42, 8, EASE.swift);
  const bandX = interpolate(frame, [2, 14], [-700, 1500], { ...clampOpt, easing: EASE.swift });
  const bandO = interpolate(frame, [2, 6, 10, 14], [0, 0.12, 0.12, 0], clampOpt);
  const stage = interpolate(frame, [42, 50, 58], [0, 0.5, 0.28], clampOpt);
  const rule = ramp(frame, 58, 12, EASE.snappy);
  const ext = ramp(frame, 66, 8, EASE.out);
  const extFade = 1 - ramp(frame, 74, 6, EASE.linear);
  const breath = interpolate(frame, [62, 66], [0, 1], clampOpt) * (1 - ramp(frame, 66, 10, EASE.out));
  const ctaIn = ramp(frame, 76, 14, EASE.snappy);
  const priceIn = ramp(frame, 86, 14, EASE.snappy);
  const bgBlur = ramp(frame, 0, 24, EASE.out) * 14;

  return (
    <AbsoluteFill style={{ background: `linear-gradient(160deg, ${C.bg} 0%, ${C.bg2} 55%, #0f0828 100%)`, overflow: 'hidden', fontFamily: FONT }}>
      {/* фон: панель в глубине резкости */}
      <AbsoluteFill style={{ filter: `blur(${bgBlur.toFixed(2)}px) brightness(0.45) saturate(1.1)`, transform: 'scale(1.15)' }}>
        <Img src={staticFile('textures/dashboard-full.png')} style={{ position: 'absolute', left: 0, top: -40, width: 1080, height: 2000 }} />
      </AbsoluteFill>
      <AbsoluteFill style={{ background: 'radial-gradient(circle at 15% 25%, rgba(192,132,252,0.30), transparent 40%), radial-gradient(circle at 85% 75%, rgba(244,114,182,0.24), transparent 45%), radial-gradient(circle at 60% 10%, rgba(56,189,248,0.16), transparent 40%)' }} />
      {/* сценический свет за логотипом */}
      <AbsoluteFill style={{ background: 'radial-gradient(ellipse 520px 300px at 50% 47%, rgba(232,121,249,0.55), rgba(168,85,247,0.18) 50%, transparent 75%)', opacity: stage, mixBlendMode: 'screen' }} />

      <AbsoluteFill style={{ perspective: 1400, perspectiveOrigin: '50% 45%' }}>
        <AbsoluteFill style={{ transform: `rotateX(${stageTilt.toFixed(3)}deg) scale(${stageScale.toFixed(4)})`, transformOrigin: '50% 50%' }}>
          {ELS.map((e, i) => {
            if (frame < e.cue) return null;
            const posAt = (f: number) => interpolate(f, [e.cue, e.cue + FLY], [0, 1], { ...clampOpt, easing: FLY_EASE });
            const t = posAt(frame);
            const x = e.cx + e.dx * (1 - t);
            const y = e.cy + e.dy * (1 - t);
            const vx = velocity((f) => e.dx * (1 - posAt(f)), frame);
            const vy = velocity((f) => e.dy * (1 - posAt(f)), frame);
            const rot = e.rot * (2 - Math.min(1, t));
            const sc = e.scale * (1.12 - 0.12 * Math.min(1, t));
            const settle = ramp(frame, e.cue + 9, 7, EASE.out);
            const press = 1 - 0.015 * Math.sin(settle * Math.PI);
            const w = e.w * sc;
            const h = e.h * sc;
            return (
              <div
                key={i}
                style={{
                  position: 'absolute', left: x - w / 2, top: y - h / 2, width: w, height: h,
                  transform: `rotate(${rot.toFixed(3)}deg) scale(${press.toFixed(4)})`,
                  opacity: Math.min(1, t * 3) * (1 - 0.12 * stepBack), filter: `saturate(${(1 - 0.08 * stepBack).toFixed(3)})`,
                }}
              >
                <SpeedBlur vx={vx} vy={vy} amount={0.3} max={22}>
                  <div
                    style={{
                      position: 'absolute', inset: 0, borderRadius: 14, overflow: 'hidden',
                      boxShadow: `0 ${(6 + 20 * (1 - settle)).toFixed(1)}px ${(18 + 40 * (1 - settle)).toFixed(1)}px rgba(4,2,12,0.55), 0 0 0 1px rgba(192,132,252,0.25)`,
                    }}
                  >
                    <Img src={staticFile(`textures/${e.file}`)} style={{ width: '100%', height: '100%', display: 'block' }} />
                  </div>
                </SpeedBlur>
              </div>
            );
          })}

          {/* блик-полоса на старте */}
          <div style={{ position: 'absolute', top: 0, bottom: 0, left: bandX, width: 600, opacity: bandO, background: 'linear-gradient(90deg, transparent, rgba(255,240,255,1), transparent)', transform: 'skewX(-14deg)' }} />

          {/* логотип */}
          <div style={{ position: 'absolute', left: 0, right: 0, top: 700, textAlign: 'center' }}>
            <div style={{ fontFamily: MONO, fontSize: 32, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.text2, opacity: ramp(frame, 50, 10, EASE.out), marginBottom: 10 }}>
              {eyebrow}
            </div>
            <div style={{ display: 'inline-flex', letterSpacing: `${(0.06 + 0.02 * breath).toFixed(4)}em`, fontSize: 196, fontWeight: 900, lineHeight: 1 }}>
              {letters.map((ch, i) => {
                const lt = ramp(frame, LETTER_DELAY(i), 8, EASE.snappy);
                const lp = interpolate(frame, [LETTER_DELAY(i) + 5, LETTER_DELAY(i) + 7, LETTER_DELAY(i) + 10], [1, 0.94, 1], clampOpt);
                return (
                  <span
                    key={i}
                    style={{
                      display: 'inline-block', opacity: lt, transform: `translateY(${((1 - lt) * -40).toFixed(2)}px) scale(${((2 - lt) * lp).toFixed(4)})`,
                      background: `linear-gradient(180deg, #ffffff 0%, ${C.pink} 70%, ${C.logo} 100%)`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
                      filter: `drop-shadow(0 0 ${(26 * lt).toFixed(1)}px rgba(232,121,249,0.55))`,
                    }}
                  >
                    {ch}
                  </span>
                );
              })}
            </div>
            {/* линия под логотипом и её продолжения */}
            <div style={{ position: 'relative', height: 4, margin: '18px auto 0', width: 620 }}>
              <div style={{ position: 'absolute', left: 310 - 310 * rule, width: 620 * rule, top: 0, height: 4, borderRadius: 2, background: `linear-gradient(90deg, ${C.logo}, ${C.cyan})` }} />
              <div style={{ position: 'absolute', right: 620, width: 190 * ext, top: 1, height: 2, background: `linear-gradient(270deg, ${C.logo}, transparent)`, opacity: extFade }} />
              <div style={{ position: 'absolute', left: 620, width: 190 * ext, top: 1, height: 2, background: `linear-gradient(90deg, ${C.cyan}, transparent)`, opacity: extFade }} />
            </div>
            {/* контакт и цена */}
            <div style={{ marginTop: 40, opacity: ctaIn, transform: `translateY(${((1 - ctaIn) * 30).toFixed(2)}px)` }}>
              <span
                style={{
                  display: 'inline-block', padding: '14px 46px', borderRadius: 999, border: `5px solid ${C.logo}`, fontSize: 76, fontWeight: 900, letterSpacing: '-0.02em',
                  color: C.pink, background: 'rgba(20,10,40,0.75)', boxShadow: '0 0 40px rgba(232,121,249,0.45), inset 0 0 24px rgba(232,121,249,0.2)',
                }}
              >
                {contact}
              </span>
              <div style={{ marginTop: 16, fontSize: 38, fontWeight: 500, color: C.text2 }}>{contactNote}</div>
            </div>
            <div style={{ marginTop: 30, opacity: priceIn, transform: `translateY(${((1 - priceIn) * 24).toFixed(2)}px)`, fontSize: 66, fontWeight: 900, color: C.cyan, textShadow: '0 0 30px rgba(103,232,249,0.35)' }}>
              {price}
            </div>
          </div>
        </AbsoluteFill>
      </AbsoluteFill>
      <Dust count={22} seed={7} opacity={0.65} from={20} />
      <Grain opacity={0.06} blend="soft-light" />
    </AbsoluteFill>
  );
};
