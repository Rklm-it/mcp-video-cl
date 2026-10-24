// Визуальный язык ролика берётся из самой панели (video-shotcraft, принцип 2):
// тема Nebula (frontend/src/app/globals.css, [data-theme="nebula"]) + фирменная
// концовка канала (docs/nexus/brand/endcard-panel.png: розовый и бирюзовый).
import { useEffect, useState } from 'react';
import { cancelRender, continueRender, delayRender, staticFile } from 'remotion';

export const W = 1080;
export const H = 1920;
export const FPS = 30;

export const C = {
  bg: '#0b0820',
  bg2: '#1a103a',
  surface: 'rgb(38,27,74)', // карточка Nebula на фоне страницы (замер по скриншоту)
  text: '#f3eaff',
  text2: '#c4b5d8',
  muted: '#8b7ca8',
  accent: '#c084fc',
  accentDim: '#a855f7',
  pink: '#f0abfc', // светлая фуксия: маркер ключевого слова, лучи
  logo: '#e879f9', // цвет логотипа в Nebula
  cyan: '#67e8f9',
  ok: '#6ee7b7',
  ink: '#1a0b2e', // тёмный текст на светлой плашке
};

export const LAMP = '236,222,255'; // холодный сиреневый свет прожектора (вместо тёплого вольфрама Ink Press)

export const FONT = "'Inter', 'DejaVu Sans', system-ui, sans-serif";
export const MONO = "'DejaVu Sans Mono', ui-monospace, monospace";

// Inter лежит в public/fonts: рендер не зависит от того, какие шрифты стоят на машине.
// Грузит их useFonts() в корневом компоненте (см. Main.tsx).
export const FONT_FACES = [
  ['500', 'Inter-Medium.otf'],
  ['700', 'Inter-Bold.otf'],
  ['800', 'Inter-ExtraBold.otf'],
  ['900', 'Inter-Black.otf'],
] as const;

/**
 * delayRender — внутри компонента, а не на уровне модуля: при вызове на импорте
 * Remotion потом сбрасывает список задержек, continueRender свою не находит,
 * и таймер снимает рендер через timeout (так падал полный рендер на 2 потоках).
 */
export const useFonts = () => {
  const [handle] = useState(() => delayRender('Шрифт Inter'));
  useEffect(() => {
    Promise.all(
      FONT_FACES.map(async ([weight, file]) => {
        const face = new FontFace('Inter', `url('${staticFile(`fonts/${file}`)}') format('opentype')`, { weight });
        await face.load();
        document.fonts.add(face);
      }),
    ).then(() => continueRender(handle), (err) => cancelRender(err));
  }, [handle]);
};

export const clampOpt = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
