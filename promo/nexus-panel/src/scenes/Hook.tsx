// Хук (2.4 с). По стилю канала (docs/nexus/style-guide.md) первый кадр — уже
// собранная обложка: вопрос/тезис на 3 строки, средняя крупнее и цветом, всё
// внутри обрезки сетки профиля 3:4 (y 240…1680). Под ним — настольная панель
// на наклонной плоскости, она медленно наезжает. Проявления с пустого фона нет.
//
// Отступление от promo-energy-arc (низкий брендовый старт): у шортсов первые
// 2 секунды решают досмотр, поэтому бренд переехал в концовку (см. README.md).
import React from 'react';
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { C, FONT, MONO, clampOpt } from '../theme';
import { EASE, Grain, ramp } from '../lib/Polish';

export const HOOK_DURATION = 72;

export const HOOK_DEFAULTS = {
  eyebrow: 'NEXUS · панель для VPN',
  lines: ['5 фишек,', 'которых нет', 'в других VPN-панелях'],
};

export const Hook: React.FC<Partial<typeof HOOK_DEFAULTS>> = (props) => {
  const { eyebrow, lines } = { ...HOOK_DEFAULTS, ...props };
  const frame = useCurrentFrame();

  // плоскость панели: наклон и медленный наезд на всём протяжении
  const push = interpolate(frame, [0, HOOK_DURATION], [0, 1], clampOpt);
  const scale = 0.66 + 0.06 * push;
  // текст уходит вверх с размытием перед склейкой
  const out = ramp(frame, 50, 16, EASE.exit);

  return (
    <AbsoluteFill style={{ background: `linear-gradient(160deg, ${C.bg} 0%, ${C.bg2} 55%, #0f0828 100%)`, overflow: 'hidden' }}>
      <AbsoluteFill style={{ perspective: 1600, perspectiveOrigin: '50% 40%' }}>
        <div
          style={{
            position: 'absolute', left: 540 - 960, top: 1180 - 540, width: 1920, height: 1080,
            transform: `scale(${scale.toFixed(4)}) rotateX(${(24 - 6 * push).toFixed(3)}deg) rotateZ(${(-9 + 2 * push).toFixed(3)}deg)`,
            transformOrigin: '50% 50%', borderRadius: 26, overflow: 'hidden',
            boxShadow: '0 60px 160px rgba(0,0,0,0.7), 0 0 0 1px rgba(192,132,252,0.25), 0 0 120px rgba(168,85,247,0.25)',
          }}
        >
          <Img src={staticFile('textures/desk-dashboard.png')} style={{ width: 1920, height: 1080, display: 'block' }} />
        </div>
      </AbsoluteFill>
      {/* затемнение сверху под текст */}
      <AbsoluteFill style={{ background: 'linear-gradient(180deg, rgba(11,8,32,0.92) 0%, rgba(11,8,32,0.78) 42%, rgba(11,8,32,0.15) 70%, rgba(11,8,32,0.55) 100%)' }} />

      <div
        style={{
          position: 'absolute', left: 70, right: 70, top: 300,
          opacity: 1 - out, transform: `translateY(${(-60 * out).toFixed(2)}px)`, filter: out > 0.01 ? `blur(${(10 * out).toFixed(2)}px)` : undefined,
          fontFamily: FONT, color: C.text,
        }}
      >
        <div style={{ fontFamily: MONO, fontSize: 34, fontWeight: 700, letterSpacing: '0.14em', color: C.text2, textTransform: 'uppercase', marginBottom: 34, display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ width: 16, height: 16, borderRadius: 4, background: C.logo, boxShadow: `0 0 18px ${C.logo}` }} />
          {eyebrow}
        </div>
        <div style={{ fontSize: 108, fontWeight: 900, lineHeight: 1.0, letterSpacing: '-0.035em', textTransform: 'uppercase' }}>{lines[0]}</div>
        <div
          style={{
            fontSize: 118, fontWeight: 900, lineHeight: 1.04, letterSpacing: '-0.045em', textTransform: 'uppercase', margin: '8px 0 12px', whiteSpace: 'nowrap',
            background: `linear-gradient(90deg, ${C.logo} 0%, ${C.pink} 55%, ${C.cyan} 120%)`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
            filter: 'drop-shadow(0 0 30px rgba(232,121,249,0.35))',
          }}
        >
          {lines[1]}
        </div>
        <div style={{ fontSize: 86, fontWeight: 900, lineHeight: 1.02, letterSpacing: '-0.035em', textTransform: 'uppercase' }}>{lines[2]}</div>
      </div>
      <Grain opacity={0.06} blend="soft-light" />
    </AbsoluteFill>
  );
};
