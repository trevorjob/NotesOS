import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';
import { Sheet } from './Sheet';

interface SelectOption {
  label: string;
  value: string;
}

interface SelectProps {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
}

export function Select({ label, value, onChange, options }: SelectProps) {
  const { c, font, size, radius, trackingUtility } = useTheme();
  const [open, setOpen] = useState(false);
  const current = options.find((o) => o.value === value);

  return (
    <View style={styles.field}>
      {label && (
        <Text style={{ fontFamily: font.utility, fontSize: size.utility, letterSpacing: trackingUtility(size.utility), textTransform: 'uppercase', color: c.inkSecondary }}>
          {label}
        </Text>
      )}
      <Pressable onPress={() => setOpen(true)} style={[styles.trigger, { borderColor: c.paperEdge, borderRadius: radius.sm, backgroundColor: c.paper }]}>
        <Text style={{ fontFamily: font.body, fontSize: size.body, color: c.ink }}>{current?.label ?? ''}</Text>
      </Pressable>
      <Sheet open={open} onClose={() => setOpen(false)} title={label}>
        {options.map((o) => (
          <Pressable
            key={o.value}
            onPress={() => {
              onChange(o.value);
              setOpen(false);
            }}
            style={[styles.option, { borderBottomColor: c.paperEdge }]}
          >
            <Text style={{ fontFamily: font.body, fontSize: size.body, color: o.value === value ? c.confirm : c.ink }}>{o.label}</Text>
          </Pressable>
        ))}
      </Sheet>
    </View>
  );
}

const styles = StyleSheet.create({
  field: { gap: 6 },
  trigger: { borderWidth: 1, paddingHorizontal: 14, paddingVertical: 12, minHeight: 44, justifyContent: 'center' },
  option: { paddingVertical: 12, borderBottomWidth: 1, minHeight: 44, justifyContent: 'center' },
});
