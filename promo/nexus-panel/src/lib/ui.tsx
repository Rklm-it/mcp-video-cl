// Общие элементы ролика: субтитр, вспышка на склейке, курсор, пыль.
import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, MONO, clampOpt } from '../theme';
import { EASE, ramp } from './Polish';

/** `*слово*` → ключевое слово на розовой плашке (как жёлтые плашки в стиле канала). */
const parse = (text: string) => text.split(/(\*[^*]+\*)/).filter(Boolean).map((part) => ({
  key: part.startsWith('*'),
  text: part.replace(/\*/g, ''),
}));

/**
 * Субтитр сцены. Читаемость по Q11: 60 px Inter ExtraBold (≥56 px на 1080×1920),
 * под ним тёмная подложка — кадр целиком занят страницей панели.
 * Стоит в зоне, которую не закрывает интерфейс Reels/Shorts (низ ~350 px и правый край).
 */
export const Caption: React.FC<{ text: string; duration: number; y?: number }> = ({ text, duration, y = 1330 }) => {
  const frame = useCurrentFrame();
  const inT = ramp(frame, 0, 9, EASE.out);
  const outT = 1 - ramp(frame, duration - 7, 7, EASE.swift);
  const lines = text.split('\n');
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      <div
        style={{
          position: 'absolute', left: 0, right: 0, top: y - 170, height: 470, opacity: inT * outT,
          background: 'linear-gradient(180deg, rgba(11,8,32,0) 0%, rgba(11,8,32,0.82) 38%, rgba(11,8,32,0.88) 70%, rgba(11,8,32,0) 100%)',
        }}
      />
      <div
        style={{
          position: 'absolute', left: 70, right: 130, top: y, display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 14,
          opacity: inT * outT, transform: `translateY(${((1 - inT) * 24).toFixed(2)}px)`,
          fontFamily: FONT, fontWeight: 800, fontSize: 60, lineHeight: 1.12, letterSpacing: '-0.02em', color: C.text,
          textShadow: '0 2px 18px rgba(0,0,0,0.55)',
        }}
      >
        {lines.map((line, li) => (
          <div key={li}>
            {parse(line).map((p, i) =>
              p.key ? (
                <span key={i} style={{ background: C.pink, color: C.ink, padding: '0 14px', borderRadius: 12, textShadow: 'none', boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone' }}>
                  {p.text}
                </span>
              ) : (
                <span key={i}>{p.text}</span>
              ),
            )}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/** Вспышка на жёсткой склейке: 5 кадров до шва и 5 после (FlashCut скилла, сиреневый вместо тёплого). */
export const FlashCut: React.FC<{ duration?: number }> = ({ duration = 10 }) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [0, duration * 0.4, duration], [0, 0.8, 0], clampOpt);
  return (
    <AbsoluteFill
      style={{
        pointerEvents: 'none', opacity: o,
        background: 'radial-gradient(ellipse at 50% 45%, rgba(250,240,255,0.98), rgba(232,190,255,0.5) 55%, transparent 82%)',
      }}
    />
  );
};

/** Курсор мыши (стрелка), размер на экране постоянный. */
export const Pointer: React.FC<{ size?: number }> = ({ size = 30 }) => (
  <svg width={size} height={size * 1.45} viewBox="0 0 20 29" style={{ overflow: 'visible', filter: 'drop-shadow(0 3px 6px rgba(0,0,0,0.5))' }}>
    <path d="M1 1 L1 23 L6.5 17.5 L10.5 27 L14 25.5 L10 16.5 L18 16.5 Z" fill="#ffffff" stroke="#120a24" strokeWidth={1.6} strokeLinejoin="round" />
  </svg>
);

/** Мелкая подпись-счётчик моноширинным (как «26 REAL PAGE CAPTURES» в deck-deal-flyin). */
export const MonoTag: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ fontFamily: MONO, fontSize: 34, fontWeight: 700, letterSpacing: '0.12em', color: C.text, textTransform: 'uppercase', ...style }}>{children}</div>
);

// Пыль/искры: все параметры выводятся из индекса — рендер воспроизводим (принцип 9).
export const Dust: React.FC<{ count?: number; seed?: number; opacity?: number; color?: string; from?: number }> = ({ count = 24, seed = 1, opacity = 0.6, color = '#f5d0fe', from = 0 }) => {
  const frame = useCurrentFrame() - from;
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      {Array.from({ length: count }, (_, i) => {
        const k = i + seed * 31;
        const x = (k * 439 + 137) % 1080;
        const y0 = (k * 613 + 271) % 1920;
        const rise = 0.5 + (k % 5) * 0.18;
        const y = (((y0 - frame * rise) % 1920) + 1920) % 1920;
        const sway = Math.sin(frame * (0.02 + (k % 3) * 0.008) + k) * (8 + (k % 4) * 5);
        const size = 2.6 + (k % 3) * 1.1;
        const tw = 0.6 + 0.4 * Math.sin(frame * 0.12 + k * 1.7);
        return (
          <div
            key={i}
            style={{
              position: 'absolute', left: x + sway, top: y, width: size, height: size, borderRadius: '50%',
              background: color, opacity: opacity * tw * (0.45 + ((k * 7) % 5) * 0.12),
              boxShadow: `0 0 ${size * 3}px ${color}`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
