import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

export type ConceptState = 'solid' | 'fading' | 'shaky';

interface StateBadgeProps {
  state?: ConceptState;
  showLabel?: boolean;
  size?: number;
}

const STATE_META: Record<ConceptState, { weight: '400' | '500' | '700'; label: string }> = {
  solid: { weight: '700', label: 'Solid' },
  fading: { weight: '500', label: 'Fading' },
  shaky: { weight: '400', label: 'Shaky' },
};

export function StateBadge({ state = 'solid', showLabel = true, size = 14 }: StateBadgeProps) {
  const { c, font, size: fontSize, trackingUtility } = useTheme();
  const color = { solid: c.stateSolid, fading: c.stateFading, shaky: c.stateShaky }[state];
  const meta = STATE_META[state];

  return (
    <View style={styles.row}>
      <View style={{ width: size, height: size, borderRadius: size / 2, borderWidth: 2, borderColor: color, backgroundColor: color }} />
      {showLabel && (
        <Text
          style={{
            fontFamily: font.utility,
            fontSize: fontSize.utility,
            letterSpacing: trackingUtility(fontSize.utility),
            textTransform: 'uppercase',
            fontWeight: meta.weight,
            color,
          }}
        >
          {meta.label}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 6 },
});
