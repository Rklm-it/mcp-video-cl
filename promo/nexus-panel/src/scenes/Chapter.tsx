// Карточка-глава: paper-title-card (video-shotcraft, demos/typography/paper-title-card)
// на фоне Nebula вместо бумаги. Слова «вдавливаются» по одному (scale 1.28 → 1,
// размытие 7 → 0), одно ключевое слово цветом, подчёркивание закрывает карточку.
// Из исходника: задержка слова 4 + i·4, 9f, bezier(0.2,0.75,0.3,1), линия 16→34f.
import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { Grain } from '../lib/Polish';
import { C, FONT, MONO, clampOpt } from '../theme';

export const CHAPTER_DURATION = 54;

const WORD_EASE = Easing.bezier(0.2, 0.75, 0.3, 1);

export const Chapter: React.FC<{ eyebrow?: string; text?: string }> = ({
  eyebrow = 'и это ещё не всё',
  // `*слово*` — ключевое; `/` — перенос строки
  text = 'Всё, что нужно / *каждый день*',
}) => {
  const frame = useCurrentFrame();
  const words = text.split(' ');
  const line = interpolate(frame, [16, 34], [0, 1], { ...clampOpt, easing: Easing.bezier(0.22, 1, 0.36, 1) });
  const out = interpolate(frame, [CHAPTER_DURATION - 8, CHAPTER_DURATION], [1, 0], clampOpt);
  let i = 0;
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse 80% 50% at 50% 45%, rgba(168,85,247,0.28), transparent 70%), linear-gradient(160deg, ${C.bg} 0%, ${C.bg2} 55%, #0f0828 100%)`, fontFamily: FONT }}>
      <div style={{ position: 'absolute', left: 80, right: 80, top: 720, opacity: out }}>
        <div style={{ fontFamily: MONO, fontSize: 34, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.text2, marginBottom: 26, opacity: interpolate(frame, [0, 8], [0, 1], clampOpt) }}>
          {eyebrow}
        </div>
        <div style={{ fontSize: 104, fontWeight: 900, lineHeight: 1.06, letterSpacing: '-0.04em', color: C.text }}>
          {words.map((w, k) => {
            if (w === '/') return <br key={k} />;
            const accent = w.startsWith('*') || w.endsWith('*');
            const d = 4 + i++ * 4;
            const t = interpolate(frame, [d, d + 9], [0, 1], { ...clampOpt, easing: WORD_EASE });
            return (
              <span
                key={k}
                style={{
                  display: 'inline-block', marginRight: '0.24em', opacity: t, transform: `scale(${(1.28 - 0.28 * t).toFixed(4)})`,
                  filter: t < 1 ? `blur(${(7 * (1 - t)).toFixed(2)}px)` : undefined, color: accent ? C.pink : C.text,
                }}
              >
                {w.replace(/\*/g, '')}
              </span>
            );
          })}
        </div>
        <div style={{ marginTop: 30, height: 8, width: 300, borderRadius: 4, transformOrigin: '0 50%', transform: `scaleX(${line.toFixed(4)})`, background: `linear-gradient(90deg, ${C.logo}, ${C.cyan})` }} />
      </div>
      <Grain opacity={0.06} blend="soft-light" />
    </AbsoluteFill>
  );
};
