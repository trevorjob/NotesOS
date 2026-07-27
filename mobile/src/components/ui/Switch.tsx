import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
}

export function Switch({ checked, onChange, label }: SwitchProps) {
  const { c, font, size, radius } = useTheme();

  return (
    <Pressable style={styles.row} onPress={() => onChange(!checked)}>
      {label && <Text style={{ fontFamily: font.body, fontSize: size.body, color: c.ink }}>{label}</Text>}
      <View style={[styles.track, { borderRadius: radius.pill, backgroundColor: checked ? c.ink : c.paperEdge }]}>
        <View style={[styles.thumb, { backgroundColor: c.paper, left: checked ? 20 : 2 }]} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 44 },
  track: { width: 40, height: 22, justifyContent: 'center' },
  thumb: { position: 'absolute', top: 2, width: 18, height: 18, borderRadius: 9 },
});
