import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

interface DividerProps {
  label?: string;
  spacing?: number;
}

export function Divider({ label, spacing }: DividerProps) {
  const { c, font, size, space, trackingUtility } = useTheme();
  const margin = spacing ?? space[5];

  if (!label) {
    return <View style={[styles.line, { borderTopColor: c.paperEdge, marginVertical: margin }]} />;
  }

  return (
    <View style={[styles.row, { marginVertical: margin }]}>
      <View style={[styles.line, styles.flex, { borderTopColor: c.paperEdge }]} />
      <Text style={{ fontFamily: font.utility, fontSize: size.utility, letterSpacing: trackingUtility(size.utility), textTransform: 'uppercase', color: c.inkTertiary }}>
        {label}
      </Text>
      <View style={[styles.line, styles.flex, { borderTopColor: c.paperEdge }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  line: { borderTopWidth: 1 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  flex: { flex: 1 },
});
