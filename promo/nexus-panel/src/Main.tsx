// Монтаж промо панели Nexus. SHOTS — единственный источник времени: субтитры,
// вспышки и звук считаются от него, поэтому при смене длины сцены всё едет само
// (video-shotcraft, pipeline.md этап 5–6).
import React from 'react';
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile } from 'remotion';
import { Dashboard, DASHBOARD_DURATION } from './scenes/Dashboard';
import { Hook, HOOK_DURATION } from './scenes/Hook';
import { Nodes, NODES_DURATION } from './scenes/Nodes';
import { Outro, OUTRO_DURATION } from './scenes/Outro';
import { Payments, PAYMENTS_DURATION } from './scenes/Payments';
import { Users, USERS_DURATION } from './scenes/Users';
import { Caption, FlashCut } from './lib/ui';
import { C, clampOpt, useFonts } from './theme';

const ORDER = [
  ['hook', HOOK_DURATION],
  ['dashboard', DASHBOARD_DURATION],
  ['nodes', NODES_DURATION],
  ['users', USERS_DURATION],
  ['payments', PAYMENTS_DURATION],
  ['outro', OUTRO_DURATION],
] as const;
type ShotId = (typeof ORDER)[number][0];

export const SHOTS = ORDER.reduce(
  (acc, [id, duration], i) => {
    const prev = i === 0 ? null : acc[ORDER[i - 1][0]];
    acc[id] = { from: prev ? prev.from + prev.duration : 0, duration };
    return acc;
  },
  {} as Record<ShotId, { from: number; duration: number }>,
);
export const TOTAL = SHOTS.outro.from + SHOTS.outro.duration;

const SCENES: Record<ShotId, React.FC> = { hook: Hook, dashboard: Dashboard, nodes: Nodes, users: Users, payments: Payments, outro: Outro };

// Субтитры (C1): у каждой сцены свой факт; у концовки субтитра нет — она чистая.
export const CAPTIONS: { from: number; duration: number; text: string }[] = [
  { from: SHOTS.dashboard.from + 96, duration: 76, text: 'Клиенты, ноды и деньги —\n*на одном экране*' },
  { from: SHOTS.nodes.from + 56, duration: 94, text: 'Все ноды и их статус —\n*в реальном времени*' },
  { from: SHOTS.users.from + 14, duration: 94, text: 'Любой клиент —\n*за секунду*' },
  { from: SHOTS.payments.from + 30, duration: 84, text: 'Оплатил — подписка\n*продлилась сама*' },
];

// Вспышка перекрывает шов: 5 кадров до и 5 после.
export const FLASH_CUTS = (['dashboard', 'nodes', 'users', 'payments', 'outro'] as const).map((id) => SHOTS[id].from - 5);

// Звук: кадр, файл, громкость; каждая строка — что происходит в кадре (S2).
// Громкость задана по пику файла (S3/sound-design 4): тихий switch-light (−10.7 dB) идёт на 1.0.
type Sfx = { from: number; src: string; volume: number; duration?: number };
const d = SHOTS.dashboard.from, n = SHOTS.nodes.from, u = SHOTS.users.from, p = SHOTS.payments.from, o = SHOTS.outro.from;
export const SFX: Sfx[] = [
  { from: 48, src: 'whoosh-fast.mp3', volume: 0.32 }, // хук уходит вверх
  ...FLASH_CUTS.map((f) => ({ from: f + 1, src: 'transition-snap.mp3', volume: 0.3 })), // склейки
  { from: d + 2, src: 'switch-light.mp3', volume: 1.0 }, // рубильник света
  { from: d + 54, src: 'whoosh-fast.mp3', volume: 0.42 }, // карточка взлетает
  { from: d + 67, src: 'sparkle-touch.mp3', volume: 0.38 }, // луч по контуру
  { from: d + 140, src: 'bass-hit-short.mp3', volume: 0.32 }, // карточка садится
  { from: n + 2, src: 'air-woosh-quick.mp3', volume: 0.28 }, // облёт колоды
  // раздача: два файла по очереди, громкость ступенями вниз; дальше плотно — одним шорохом
  { from: n + 36, src: 'sweep-fast-small.mp3', volume: 0.4 },
  { from: n + 42, src: 'air-woosh-quick.mp3', volume: 0.34 },
  { from: n + 47, src: 'sweep-fast-small.mp3', volume: 0.3 },
  { from: n + 51, src: 'whoosh-electric.mp3', volume: 0.3, duration: 40 },
  { from: u + 10, src: 'typewriter-digital.mp3', volume: 0.4, duration: 13 }, // набор «ivan»
  { from: u + 40, src: 'air-woosh-quick.mp3', volume: 0.22 }, // строки уходят
  { from: u + 59, src: 'click-camera.mp3', volume: 0.55 }, // щелчок по строке
  { from: u + 60, src: 'whoosh-fast.mp3', volume: 0.22 }, // наезд
  ...[8, 20, 32, 44, 56, 68].map((c, i) => ({ from: p + c + 18, src: i % 2 ? 'air-woosh-quick.mp3' : 'sweep-fast-small.mp3', volume: 0.36 - i * 0.03 })), // строки садятся
  { from: p + 91, src: 'shimmer-sparkle-sweep.mp3', volume: 0.28, duration: 40 }, // блик
  { from: o, src: 'stardust-swish.mp3', volume: 0.32, duration: 46 }, // разгон перед логотипом
  { from: o + 4, src: 'whoosh-fast.mp3', volume: 0.36 }, // элементы слетаются
  { from: o + 46, src: 'impact-epic-trailer.mp3', volume: 0.55 }, // логотип вдавлен — пик громкости
  { from: o + 58, src: 'sparkle-touch.mp3', volume: 0.34 }, // искры
];

const BGM_START = 60; // в треке с 2-й секунды уже полный бит

export const Main: React.FC<{ bgm?: boolean }> = ({ bgm = true }) => {
  useFonts();
  return (
  <AbsoluteFill style={{ background: C.bg }}>
    {ORDER.map(([id]) => {
      const Scene = SCENES[id];
      return (
        <Sequence key={id} from={SHOTS[id].from} durationInFrames={SHOTS[id].duration} name={id}>
          <Scene />
        </Sequence>
      );
    })}
    {CAPTIONS.map((c, i) => (
      <Sequence key={`cap${i}`} from={c.from} durationInFrames={c.duration} name={`caption ${i + 1}`}>
        <Caption text={c.text} duration={c.duration} />
      </Sequence>
    ))}
    {FLASH_CUTS.map((f) => (
      <Sequence key={`flash${f}`} from={f} durationInFrames={10} name="flash">
        <FlashCut />
      </Sequence>
    ))}
    {SFX.map((s, i) => (
      <Sequence key={`sfx${i}`} from={s.from} durationInFrames={s.duration} name={`sfx ${s.src}`}>
        <Audio src={staticFile(`audio/${s.src}`)} volume={s.volume} />
      </Sequence>
    ))}
    {bgm ? (
      <Audio
        src={staticFile('audio/house-vibez.mp3')}
        startFrom={BGM_START}
        volume={(f) => 0.3 * interpolate(f, [0, 12, TOTAL - 36, TOTAL - 4], [0.6, 1, 1, 0], clampOpt)}
      />
    ) : null}
  </AbsoluteFill>
  );
};
