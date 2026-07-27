import React, { useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

interface TextareaProps {
  label?: string;
  placeholder?: string;
  value: string;
  onChangeText: (value: string) => void;
  rows?: number;
}

export function Textarea({ label, placeholder, value, onChangeText, rows = 4 }: TextareaProps) {
  const { c, font, size, lineHeight, radius, trackingUtility } = useTheme();
  const [focused, setFocused] = useState(false);

  return (
    <View style={styles.field}>
      {label && (
        <Text style={{ fontFamily: font.utility, fontSize: size.utility, letterSpacing: trackingUtility(size.utility), textTransform: 'uppercase', color: c.inkSecondary }}>
          {label}
        </Text>
      )}
      <TextInput
        multiline
        numberOfLines={rows}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={c.inkTertiary}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={[
          styles.input,
          {
            fontFamily: font.body,
            fontSize: size.body,
            lineHeight: size.body * lineHeight.body,
            color: c.ink,
            backgroundColor: c.paper,
            borderRadius: radius.sm,
            borderColor: focused ? c.ink : c.paperEdge,
            minHeight: rows * size.body * lineHeight.body + 24,
          },
        ]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  field: { gap: 6 },
  input: { borderWidth: 1, paddingHorizontal: 14, paddingVertical: 12, textAlignVertical: 'top' },
});
