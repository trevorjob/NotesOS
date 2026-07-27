import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

interface RadioProps {
  label: string;
  checked: boolean;
  onPress: () => void;
}

export function Radio({ label, checked, onPress }: RadioProps) {
  const { c, font, size } = useTheme();

  return (
    <Pressable style={styles.row} onPress={onPress}>
      <View style={[styles.dot, { borderColor: c.ink }]}>{checked && <View style={[styles.fill, { backgroundColor: c.ink }]} />}</View>
      <Text style={{ fontFamily: font.body, fontSize: size.body, color: c.ink }}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 44 },
  dot: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  fill: { width: 10, height: 10, borderRadius: 5 },
});
