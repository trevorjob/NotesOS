import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

interface ToastProps {
  children: string;
  state?: 'info' | 'syncing';
}

export function Toast({ children, state = 'info' }: ToastProps) {
  const { c, font, size, radius, hardShadow } = useTheme();

  return (
    <View style={[styles.base, { backgroundColor: c.ink, borderRadius: radius.md }, hardShadow(c.inkTertiary, 2)]}>
      {state === 'syncing' && <View style={[styles.dot, { backgroundColor: c.highlighter }]} />}
      <Text style={{ color: c.paper, fontFamily: font.body, fontSize: size.bodySm }}>{children}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  base: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingVertical: 12, maxWidth: 360, alignSelf: 'flex-start' },
  dot: { width: 8, height: 8, borderRadius: 4 },
});
