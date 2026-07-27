import React, { useState } from 'react';
import { StyleSheet, Text, TextInput, TextInputProps, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

interface InputProps extends Pick<TextInputProps, 'keyboardType' | 'autoFocus' | 'secureTextEntry' | 'autoCapitalize'> {
  label?: string;
  placeholder?: string;
  value: string;
  onChangeText: (value: string) => void;
  error?: string;
}

export function Input({ label, placeholder, value, onChangeText, error, ...rest }: InputProps) {
  const { c, font, size, radius, trackingUtility } = useTheme();
  const [focused, setFocused] = useState(false);

  return (
    <View style={styles.field}>
      {label && (
        <Text style={{ fontFamily: font.utility, fontSize: size.utility, letterSpacing: trackingUtility(size.utility), textTransform: 'uppercase', color: c.inkSecondary }}>
          {label}
        </Text>
      )}
      <TextInput
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
            color: c.ink,
            backgroundColor: c.paper,
            borderRadius: radius.sm,
            borderColor: error ? c.stateShaky : focused ? c.ink : c.paperEdge,
          },
        ]}
        {...rest}
      />
      {error && <Text style={{ fontSize: size.caption, color: c.stateShaky }}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  field: { gap: 6 },
  input: { borderWidth: 1, paddingHorizontal: 14, paddingVertical: 12, minHeight: 44 },
});
