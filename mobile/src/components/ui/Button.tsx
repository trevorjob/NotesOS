import React from 'react';
import { Pressable, StyleProp, StyleSheet, Text, ViewStyle } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'text';

interface ButtonProps {
  label: string;
  variant?: ButtonVariant;
  size?: 'sm' | 'md';
  disabled?: boolean;
  icon?: React.ReactNode;
  onPress?: () => void;
  style?: StyleProp<ViewStyle>;
}

export function Button({ label, variant = 'primary', size = 'md', disabled, icon, onPress, style }: ButtonProps) {
  const { c, font, radius, hardShadow } = useTheme();

  const variants: Record<ButtonVariant, ViewStyle & { textColor: string }> = {
    primary: { backgroundColor: c.ink, borderColor: c.ink, borderWidth: 1, textColor: c.paper, ...hardShadow(c.paperEdge) },
    secondary: { backgroundColor: c.paper, borderColor: c.paperEdge, borderWidth: 1, textColor: c.ink },
    ghost: { backgroundColor: 'transparent', borderColor: 'transparent', borderWidth: 1, textColor: c.ink },
    text: { backgroundColor: 'transparent', borderWidth: 0, textColor: c.confirm },
  };
  const v = variants[variant];

  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.base,
        size === 'sm' ? styles.sm : styles.md,
        { backgroundColor: v.backgroundColor, borderColor: v.borderColor, borderWidth: v.borderWidth, borderRadius: radius.md },
        variant === 'primary' && { shadowColor: v.shadowColor, shadowOffset: v.shadowOffset, shadowOpacity: v.shadowOpacity, shadowRadius: v.shadowRadius, elevation: v.elevation },
        disabled && styles.disabled,
        pressed && !disabled && styles.pressed,
        style,
      ]}
    >
      {icon}
      <Text
        style={[
          { color: v.textColor, fontFamily: font.bodySemibold, fontSize: size === 'sm' ? 14 : 16 },
          variant === 'text' && styles.underline,
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, minHeight: 44 },
  sm: { paddingHorizontal: 14, paddingVertical: 8 },
  md: { paddingHorizontal: 22, paddingVertical: 12 },
  disabled: { opacity: 0.4 },
  pressed: { transform: [{ translateX: 1 }, { translateY: 1 }] },
  underline: { textDecorationLine: 'underline' },
});
