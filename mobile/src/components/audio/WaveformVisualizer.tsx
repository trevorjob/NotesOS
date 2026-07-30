import React, { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

interface WaveformVisualizerProps {
  playing: boolean;
  barCount?: number;
  height?: number;
}

// Deterministic per-bar jitter so the resting silhouette itself reads as a
// hand-sketched wave rather than a flat equalizer — same ethos as the app's
// ink-line illustrations (irregular, never a perfectly even shape).
function seededJitter(index: number): number {
  const x = Math.sin(index * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

interface Bar {
  base: number;
  value: Animated.Value;
  duration: number;
  delay: number;
  tilt: number;
}

function buildBars(barCount: number): Bar[] {
  return Array.from({ length: barCount }, (_, i) => {
    const wave = Math.abs(Math.sin(i * 0.65));
    const base = Math.min(1, 0.3 + wave * 0.5 + seededJitter(i) * 0.3);
    return {
      base,
      value: new Animated.Value(base),
      duration: 480 + Math.round(seededJitter(i + 100) * 420),
      delay: Math.round(seededJitter(i + 200) * 300),
      tilt: (seededJitter(i + 300) - 0.5) * 4,
    };
  });
}

/** A decorative, hand-drawn-style waveform — bars dance while playing and
 * freeze mid-bounce when paused. Not amplitude-driven (expo-audio exposes no
 * metering data); the wave shape is a fixed, irregular silhouette instead. */
export function WaveformVisualizer({ playing, barCount = 27, height = 64 }: WaveformVisualizerProps) {
  const { c } = useTheme();
  const barColor = playing ? c.highlighter : c.inkTertiary;
  const bars = useMemo(() => buildBars(barCount), [barCount]);
  const loopsRef = useRef<Animated.CompositeAnimation[]>([]);

  useEffect(() => {
    if (playing) {
      loopsRef.current = bars.map((bar) => {
        const peak = Math.min(1, bar.base * 1.7 + 0.15);
        const trough = Math.max(0.15, bar.base * 0.45);
        const loop = Animated.loop(
          Animated.sequence([
            Animated.timing(bar.value, {
              toValue: peak,
              duration: bar.duration,
              delay: bar.delay,
              easing: Easing.inOut(Easing.sin),
              useNativeDriver: true,
            }),
            Animated.timing(bar.value, {
              toValue: trough,
              duration: bar.duration,
              easing: Easing.inOut(Easing.sin),
              useNativeDriver: true,
            }),
          ])
        );
        loop.start();
        return loop;
      });
    } else {
      loopsRef.current.forEach((loop) => loop.stop());
      loopsRef.current = [];
    }
    return () => {
      loopsRef.current.forEach((loop) => loop.stop());
    };
  }, [playing, bars]);

  return (
    <View
      style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', height, gap: 3 }}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      {bars.map((bar, i) => (
        <Animated.View
          key={i}
          style={{
            width: 3,
            height,
            borderRadius: 2,
            backgroundColor: barColor,
            transform: [{ scaleY: bar.value }, { rotate: `${bar.tilt}deg` }],
          }}
        />
      ))}
    </View>
  );
}
