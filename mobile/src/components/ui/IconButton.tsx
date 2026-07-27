import React from 'react';
import { Pressable, StyleSheet } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

interface IconButtonProps {
  icon: React.ReactNode;
  size?: number;
  label: string;
  active?: boolean;
  onPress?: () => void;
}

export function IconButton({ icon, size = 44, label, active, onPress }: IconButtonProps) {
  const { c, radius } = useTheme();
  const dimension = Math.max(size, 44);

  return (
    <Pressable
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [
        styles.base,
        {
          width: dimension,
          height: dimension,
          borderRadius: radius.md,
          backgroundColor: active ? c.highlighterTint : 'transparent',
          borderColor: active ? c.highlighter : 'transparent',
        },
        pressed && styles.pressed,
      ]}
    >
      {icon}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: { alignItems: 'center', justifyContent: 'center', borderWidth: 1 },
  pressed: { transform: [{ translateX: 1 }, { translateY: 1 }] },
});
