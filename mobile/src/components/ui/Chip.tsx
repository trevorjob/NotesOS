import React from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

export type ChipVariant = 'neutral' | 'correct' | 'partial' | 'needs-review';

interface ChipProps {
  label: string;
  variant?: ChipVariant;
  selected?: boolean;
  onPress?: () => void;
}

export function Chip({ label, variant = 'neutral', selected, onPress }: ChipProps) {
  const { c, font, size, radius, trackingUtility } = useTheme();

  const variants: Record<ChipVariant, { backgroundColor: string; color: string; borderColor?: string }> = {
    neutral: { backgroundColor: c.paperRecessed, color: c.inkSecondary },
    correct: { backgroundColor: 'transparent', color: c.confirm, borderColor: c.confirm },
    partial: { backgroundColor: 'transparent', color: c.stateFading, borderColor: c.stateFading },
    'needs-review': { backgroundColor: 'transparent', color: c.stateShaky, borderColor: c.stateShaky },
  };
  const v = variants[variant];

  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      style={[
        styles.base,
        { backgroundColor: v.backgroundColor, borderRadius: radius.sm, borderColor: v.borderColor ?? 'transparent', borderWidth: v.borderColor ? 1 : 0 },
        selected && { borderWidth: 2, borderColor: c.highlighter },
      ]}
    >
      <Text style={{ fontFamily: font.utility, fontSize: size.utility, letterSpacing: trackingUtility(size.utility), textTransform: 'uppercase', color: v.color }}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: { paddingHorizontal: 12, paddingVertical: 6, alignSelf: 'flex-start' },
});
