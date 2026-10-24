// Клиенты: type-and-filter (video-shotcraft, demos/interaction/type-and-filter).
// Камера у поля поиска, «ivan» набирается со скоростью руки (3f на символ),
// вдох, общий план — остальные строки уходят, нужная строка поднимается на
// первое место, курсор щёлкает по ней, камера наезжает.
//
// Из исходника: 3f на символ, курсор горит при наборе и мигает 8f после,
// кольцо фокуса, 11f вдоха, уход строк вразбежку с погружением и размытием,
// подъём цели 10f bezier(0.35,0,0.2,1) с отрывом и тенью, двойная рябь щелчка,
// наезд 16f. Переделано: строки таблицы вместо карточек, мобильная страница.
import React from 'react';
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import layout from '../layout.json';
import { CamKey, PageCam, camAt } from '../lib/Cam';
import { Grain, velocity } from '../lib/Polish';
import { Pointer } from '../lib/ui';
import { C, FONT, clampOpt } from '../theme';

export const USERS_DURATION = 108;

export const USERS_DEFAULTS = { query: 'ivan' };

const PAGE_W = layout.width;
const PAGE_H = layout.users.pageH;
const ROWS = layout.users.rows;
const TARGET = layout.users.target;
const SEARCH = layout.users.search;
const COUNT = layout.users.count;
const SLOT_Y = ROWS[0].y;
const TYPE_START = 10;
const FILTER_START = 40;
const CLICK = 60;
const FIELD = 'rgb(27,18,54)'; // заливка поля поиска (замер по скриншоту)
const PAGE_BG = 'rgb(24,17,51)';

const tgt = ROWS[TARGET];
const CLICK_C = { x: tgt.x + 150, y: SLOT_Y + tgt.h / 2 };

const CAM_KEYS: CamKey[] = [
  { frame: 0, cx: 182, cy: 600, zoom: 3.1 },
  { frame: 34, cx: 182, cy: 600, zoom: 3.1 },
  { frame: 46, cx: 270, cy: 860, zoom: 2 },
  { frame: CLICK, cx: 270, cy: 860, zoom: 2 },
  { frame: CLICK + 16, cx: 270, cy: CLICK_C.y + 40, zoom: 2.75 },
  { frame: USERS_DURATION, cx: 270, cy: CLICK_C.y + 40, zoom: 2.78 },
];
const PTR_FROM = { x: 430, y: 1180 };

export const Users: React.FC<Partial<typeof USERS_DEFAULTS>> = (props) => {
  const { query } = { ...USERS_DEFAULTS, ...props };
  const frame = useCurrentFrame();
  const cam = camAt(CAM_KEYS, frame);

  const typed = frame < TYPE_START ? 0 : Math.min(query.length, Math.floor((frame - TYPE_START) / 3) + 1);
  const caretOn = frame >= TYPE_START - 2 && frame <= CLICK + 8 && (frame <= TYPE_START + 3 * query.length + 2 || Math.floor((frame - (TYPE_START + 3 * query.length + 2)) / 8) % 2 === 0);
  const focus = interpolate(frame, [TYPE_START - 6, TYPE_START - 2, CLICK, CLICK + 6], [0, 1, 1, 0], clampOpt);

  const slideAt = (f: number) => interpolate(f, [FILTER_START, FILTER_START + 10], [0, 1], { ...clampOpt, easing: Easing.bezier(0.35, 0, 0.2, 1) });
  const slideT = slideAt(frame);
  const slideV = velocity((f) => (SLOT_Y - tgt.y) * slideAt(f), frame);
  const lift = Math.sin(slideT * Math.PI);

  const ptrT = interpolate(frame, [46, 57], [0, 1], { ...clampOpt, easing: Easing.bezier(0.45, 0, 0.2, 1) });
  const ptr = { x: PTR_FROM.x + (CLICK_C.x - PTR_FROM.x) * ptrT, y: PTR_FROM.y + (CLICK_C.y - PTR_FROM.y) * ptrT };
  const ptrO = interpolate(frame, [42, 47, CLICK + 4, CLICK + 9], [0, 1, 1, 0], clampOpt);
  const ptrPress = interpolate(frame, [CLICK - 1, CLICK + 1, CLICK + 5], [1, 0.86, 1], clampOpt);
  const picked = interpolate(frame, [CLICK + 2, CLICK + 5], [0, 1], clampOpt);

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <PageCam src="textures/users-empty.png" pageW={PAGE_W} pageH={PAGE_H} cam={cam}>
        {/* остальные строки уходят по порядку чтения */}
        {ROWS.map((r, i) => {
          if (i === TARGET) return null;
          const rank = i < TARGET ? i : i - 1;
          const outCue = FILTER_START + rank * 1.2;
          if (frame >= outCue + 6) return null;
          const outT = interpolate(frame, [outCue, outCue + 6], [0, 1], { ...clampOpt, easing: Easing.inOut(Easing.quad) });
          return (
            <div
              key={r.file}
              style={{
                position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, opacity: 1 - outT,
                transform: `translateY(${(6 * outT).toFixed(2)}px) scale(${1 - 0.015 * outT})`,
                filter: outT > 0.02 ? `blur(${(1.2 * outT).toFixed(2)}px)` : undefined,
              }}
            >
              <Img src={staticFile(`textures/${r.file}`)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
            </div>
          );
        })}

        {/* найденная строка поднимается на первое место */}
        <div
          style={{
            position: 'absolute', left: tgt.x, top: tgt.y + (SLOT_Y - tgt.y) * slideT, width: tgt.w, height: tgt.h,
            transform: `scale(${(1 + 0.02 * lift + 0.01 * picked * interpolate(frame, [CLICK + 2, CLICK + 7], [1, 0], clampOpt)).toFixed(4)})`,
            boxShadow: `0 ${(4 + 14 * lift).toFixed(1)}px ${(10 + 26 * lift).toFixed(1)}px rgba(4,2,12,${(0.25 + 0.3 * lift).toFixed(3)})`,
            borderRadius: 8, overflow: 'hidden',
            filter: Math.abs(slideV) > 4 ? `blur(${Math.min(2.4, Math.abs(slideV) * 0.04).toFixed(2)}px)` : undefined,
          }}
        >
          <Img src={staticFile(`textures/${tgt.file}`)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
          <div style={{ position: 'absolute', inset: 0, borderRadius: 8, boxShadow: `inset 0 0 0 1.5px rgba(240,171,252,${picked.toFixed(3)}), 0 0 16px rgba(232,121,249,${(0.35 * picked).toFixed(3)})`, background: `rgba(192,132,252,${(0.08 * picked).toFixed(3)})` }} />
        </div>

        {/* поле поиска: заливка поверх подсказки, набранный текст и курсор */}
        <div
          style={{
            position: 'absolute', left: SEARCH.x + 30, top: SEARCH.y + 4, width: SEARCH.w - 36, height: SEARCH.h - 8,
            background: FIELD, display: 'flex', alignItems: 'center', gap: 1,
            fontFamily: FONT, fontSize: 14, fontWeight: 500, color: C.text, opacity: frame >= TYPE_START - 2 ? 1 : 0,
          }}
        >
          <span>{query.slice(0, typed)}</span>
          {caretOn ? <span style={{ width: 1.2, height: 16, background: C.accent }} /> : null}
        </div>
        <div
          style={{
            position: 'absolute', left: SEARCH.x - 1, top: SEARCH.y - 1, width: SEARCH.w + 2, height: SEARCH.h + 2, borderRadius: 9,
            boxShadow: `0 0 0 1.5px rgba(192,132,252,${(0.9 * focus).toFixed(3)}), 0 0 12px rgba(192,132,252,${(0.35 * focus).toFixed(3)})`,
          }}
        />

        {/* счётчик над таблицей следует за фильтром */}
        {COUNT && frame >= FILTER_START ? (
          <div
            style={{
              position: 'absolute', left: COUNT.x - 30, top: COUNT.y - 2, width: COUNT.w + 32, height: COUNT.h + 4, background: PAGE_BG,
              display: 'flex', alignItems: 'center', justifyContent: 'flex-end', fontFamily: FONT, fontSize: 14, fontWeight: 500, color: C.muted,
              opacity: interpolate(frame, [FILTER_START, FILTER_START + 6], [0, 1], clampOpt),
            }}
          >
            Найдено: 1
          </div>
        ) : null}

        {/* двойная рябь щелчка */}
        {[0, 1].map((k) => {
          const start = CLICK + k * 3;
          if (frame < start || frame > start + 10) return null;
          const t = interpolate(frame, [start, start + 10], [0, 1], { ...clampOpt, easing: Easing.out(Easing.cubic) });
          const rad = interpolate(t, [0, 1], [6, k === 0 ? 26 : 38]);
          return (
            <div
              key={k}
              style={{
                position: 'absolute', left: CLICK_C.x - rad, top: CLICK_C.y - rad, width: rad * 2, height: rad * 2, borderRadius: '50%',
                border: `${k === 0 ? 1.2 : 0.9}px solid ${C.pink}`, opacity: 1 - t, boxSizing: 'border-box',
              }}
            />
          );
        })}

        {/* курсор: размер на экране постоянный */}
        {ptrO > 0.01 ? (
          <div style={{ position: 'absolute', left: ptr.x, top: ptr.y, opacity: ptrO, transform: `scale(${(ptrPress / cam.zoom).toFixed(4)})`, transformOrigin: '0 0' }}>
            <Pointer size={34} />
          </div>
        ) : null}
      </PageCam>
      <Grain opacity={0.05} blend="soft-light" />
    </AbsoluteFill>
  );
};
