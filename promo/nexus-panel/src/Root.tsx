import React from 'react';
import { Composition } from 'remotion';
import { Main, TOTAL } from './Main';
import { FPS, H, W } from './theme';

export const RemotionRoot: React.FC = () => (
  <Composition id="NexusPromo" component={Main} durationInFrames={TOTAL} fps={FPS} width={W} height={H} defaultProps={{ bgm: true }} />
);
