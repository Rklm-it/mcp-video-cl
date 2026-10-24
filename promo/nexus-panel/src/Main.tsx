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
import { Cdn, CDN_DURATION } from './scenes/Cdn';
import { Routing, ROUTING_DURATION } from './scenes/Routing';
import { StateAi, STATE_AI_DURATION } from './scenes/StateAi';
import { Updates, UPDATES_DURATION } from './scenes/Updates';
import { Migrate, MIGRATE_DURATION } from './scenes/Migrate';
import { Chapter, CHAPTER_DURATION } from './scenes/Chapter';
import { Caption, FeatureHeader, FlashCut } from './lib/ui';
import { C, clampOpt, useFonts } from './theme';

// Сначала то, чего нет у других (5 фишек, обещанных в хуке), потом — ежедневное.
const ORDER = [
  ['hook', HOOK_DURATION],
  ['cdn', CDN_DURATION],
  ['routing', ROUTING_DURATION],
  ['stateAi', STATE_AI_DURATION],
  ['updates', UPDATES_DURATION],
  ['migrate', MIGRATE_DURATION],
  ['chapter', CHAPTER_DURATION],
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

const SCENES: Record<ShotId, React.FC> = {
  hook: Hook, cdn: Cdn, routing: Routing, stateAi: StateAi, updates: Updates, migrate: Migrate, chapter: Chapter,
  dashboard: Dashboard, nodes: Nodes, users: Users, payments: Payments, outro: Outro,
};

// Заголовки фишек: номер, название и выгода — вместо нижнего субтитра (см. FeatureHeader).
export const FEATURES: { shot: ShotId; title: string; sub: string }[] = [
  { shot: 'cdn', title: 'Маскировка через\nроссийские CDN', sub: 'VPN работает даже\nпри *белых списках*' },
  { shot: 'routing', title: 'Маршруты\nпо сервисам', sub: 'Банки — через Россию,\n*Telegram и ИИ — через Европу*' },
  { shot: 'stateAi', title: 'Центр состояния\n+ ИИ-разбор', sub: 'Панель сама находит проблемы,\n*ИИ говорит, что чинить*' },
  { shot: 'updates', title: 'Обновление\nвсех нод', sub: 'Одной кнопкой.\n*Ошибка — откат сам*' },
  { shot: 'migrate', title: 'Переезд\nс других панелей', sub: 'Remnawave, Marzban, 3x-ui, Hiddify —\n*клиенты со сроками*' },
];

// Субтитры (C1): у каждой сцены свой факт; у концовки субтитра нет — она чистая.
export const CAPTIONS: { from: number; duration: number; text: string }[] = [
  { from: SHOTS.dashboard.from + 96, duration: 76, text: 'Клиенты, ноды и деньги —\n*на одном экране*' },
  { from: SHOTS.nodes.from + 56, duration: 94, text: 'Все ноды и их статус —\n*в реальном времени*' },
  { from: SHOTS.users.from + 14, duration: 94, text: 'Любой клиент —\n*за секунду*' },
  { from: SHOTS.payments.from + 30, duration: 84, text: 'Оплатил — подписка\n*продлилась сама*' },
];

// Вспышка перекрывает шов: 5 кадров до и 5 после.
export const FLASH_CUTS = ORDER.slice(1).map(([id]) => SHOTS[id].from - 5);

// Звук: кадр, файл, громкость; каждая строка — что происходит в кадре (S2).
// Громкость задана по пику файла (S3/sound-design 4): тихий switch-light (−10.7 dB) идёт на 1.0.
type Sfx = { from: number; src: string; volume: number; duration?: number };
const d = SHOTS.dashboard.from, n = SHOTS.nodes.from, u = SHOTS.users.from, p = SHOTS.payments.from, o = SHOTS.outro.from;
const cd = SHOTS.cdn.from, rt = SHOTS.routing.from, st = SHOTS.stateAi.from, up = SHOTS.updates.from, mg = SHOTS.migrate.from;
const step = (base: number, cues: number[], src: string, v0: number) => cues.map((c, i) => ({ from: base + c, src, volume: v0 - i * 0.04 }));
export const SFX: Sfx[] = [
  // 01 CDN: линия схемы, «белые списки», адреса въезжают
  { from: cd + 16, src: 'whoosh-electric.mp3', volume: 0.26, duration: 30 },
  { from: cd + 44, src: 'sparkle-touch.mp3', volume: 0.32 },
  ...step(cd, [56, 64, 72, 80], 'sweep-fast-small.mp3', 0.34),
  // 02 маршруты: щелчки по чипам, прокрутка, правила встают
  ...step(rt, [18, 36, 54, 90], 'click-camera.mp3', 0.5),
  { from: rt + 64, src: 'air-woosh-quick.mp3', volume: 0.2 },
  ...step(rt, [110, 116, 122, 128], 'sweep-fast-small.mp3', 0.32),
  // 03 центр состояния: прицел, два щелчка, ИИ печатает
  { from: st + 26, src: 'air-woosh-quick.mp3', volume: 0.2 },
  { from: st + 61, src: 'click-camera.mp3', volume: 0.48 },
  { from: st + 79, src: 'click-camera.mp3', volume: 0.48 },
  { from: st + 92, src: 'typewriter-digital.mp3', volume: 0.34, duration: 54 },
  // 04 обновление: щелчок, шаги хода, «готово» у всех
  { from: up + 21, src: 'click-camera.mp3', volume: 0.5 },
  ...step(up, [24, 50, 76], 'sweep-fast-small.mp3', 0.26),
  { from: up + 102, src: 'sparkle-touch.mp3', volume: 0.36 },
  // 05 переезд: линии подключаются, Nexus «глотает», плитки въезжают
  { from: mg + 3, src: 'whoosh-electric.mp3', volume: 0.24, duration: 34 },
  { from: mg + 52, src: 'bass-hit-short.mp3', volume: 0.36 },
  ...step(mg, [80, 86, 92, 98, 104], 'sweep-fast-small.mp3', 0.3),
  { from: SHOTS.chapter.from + 2, src: 'whoosh-fast.mp3', volume: 0.3 }, // карточка-глава
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
    {FEATURES.map((f, i) => (
      <Sequence key={`feat${i}`} from={SHOTS[f.shot].from} durationInFrames={SHOTS[f.shot].duration} name={`фишка ${i + 1}`}>
        <FeatureHeader n={i + 1} total={FEATURES.length} title={f.title} sub={f.sub} duration={SHOTS[f.shot].duration} />
      </Sequence>
    ))}
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
