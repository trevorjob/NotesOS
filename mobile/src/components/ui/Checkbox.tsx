import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

interface CheckboxProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

export function Checkbox({ label, checked, onChange }: CheckboxProps) {
  const { c, font, size, radius } = useTheme();

  return (
    <Pressable style={styles.row} onPress={() => onChange(!checked)}>
      <View style={[styles.box, { borderRadius: radius.sm, borderColor: c.ink, backgroundColor: checked ? c.ink : 'transparent' }]}>
        {checked && <View style={[styles.fill, { backgroundColor: c.paper }]} />}
      </View>
      <Text style={{ fontFamily: font.body, fontSize: size.body, color: c.ink }}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 44 },
  box: { width: 20, height: 20, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  fill: { width: 8, height: 8 },
});
