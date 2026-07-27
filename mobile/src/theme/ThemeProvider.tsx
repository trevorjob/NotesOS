import React, { createContext, useContext } from 'react';
import { useColorScheme } from 'react-native';
import { font, hardShadow, lineHeight, motion, Palette, palettes, radius, size, space, ThemeName, trackingUtility } from './tokens';

interface ThemeContextValue {
  name: ThemeName;
  c: Palette;
  font: typeof font;
  size: typeof size;
  lineHeight: typeof lineHeight;
  trackingUtility: typeof trackingUtility;
  space: typeof space;
  radius: typeof radius;
  motion: typeof motion;
  hardShadow: typeof hardShadow;
}

const ThemeContext = createContext<ThemeContextValue>({
  name: 'light',
  c: palettes.light,
  font,
  size,
  lineHeight,
  trackingUtility,
  space,
  radius,
  motion,
  hardShadow,
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const scheme = useColorScheme();
  const name: ThemeName = scheme === 'dark' ? 'dark' : 'light';
  return (
    <ThemeContext.Provider
      value={{ name, c: palettes[name], font, size, lineHeight, trackingUtility, space, radius, motion, hardShadow }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
