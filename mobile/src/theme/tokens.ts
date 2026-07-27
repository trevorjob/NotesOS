// Riso-print design tokens, ported 1:1 from the Claude Design "NotesOS Design System"
// project (tokens/*.css). Source of truth: design system project 570a44da, not this file —
// update there first, then re-port.

export type ThemeName = 'light' | 'dark';

export interface Palette {
  paper: string;
  paperRecessed: string;
  paperEdge: string;
  ink: string;
  inkSecondary: string;
  inkTertiary: string;
  stateSolid: string;
  stateFading: string;
  stateShaky: string;
  confirm: string;
  highlighter: string;
  highlighterTint: string;
}

export const light: Palette = {
  paper: '#F3ECDD',
  paperRecessed: '#EAE0C8',
  paperEdge: '#C9B99A',
  ink: '#2A2420',
  inkSecondary: '#6B6255',
  inkTertiary: '#8F8676',
  stateSolid: '#3F6E5C',
  stateFading: '#B8935B',
  stateShaky: '#B5533C',
  confirm: '#4A7A8C',
  highlighter: '#EFA83A',
  highlighterTint: '#F6D9A4',
};

export const dark: Palette = {
  paper: '#1E1B17',
  paperRecessed: '#262220',
  paperEdge: '#3A342C',
  ink: '#EDE6D6',
  inkSecondary: '#A79C89',
  inkTertiary: '#7C7364',
  stateSolid: '#5FA085',
  stateFading: '#D7A461',
  stateShaky: '#D97A5E',
  confirm: '#6FA8B8',
  highlighter: '#F2B54E',
  highlighterTint: '#4A3A22',
};

export const palettes: Record<ThemeName, Palette> = { light, dark };

export const font = {
  display: 'Newsreader_500Medium',
  displayItalic: 'Newsreader_400Regular_Italic',
  math: 'Newsreader_400Regular_Italic',
  body: 'Archivo_400Regular',
  bodyMedium: 'Archivo_500Medium',
  bodySemibold: 'Archivo_600SemiBold',
  bodyBold: 'Archivo_700Bold',
  utility: 'Archivo_600SemiBold',
};

export const size = {
  display1: 44,
  display2: 32,
  display3: 26,
  bodyLg: 19,
  body: 17,
  bodySm: 15,
  utility: 13,
  caption: 12,
};

export const lineHeight = {
  display: 1.15,
  body: 1.55,
  utility: 1.3,
};

// tracking-utility is 0.06em in the source CSS; RN letterSpacing is absolute points,
// so convert per font size at the call site with trackingUtility(size).
export const trackingUtility = (fontSize: number) => Math.round(fontSize * 0.06 * 10) / 10;

export const space = {
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 24,
  6: 32,
  7: 48,
  8: 64,
  9: 96,
  gutterPage: 20,
  gapSection: 32,
  baseline: 28,
};

export const radius = {
  sm: 2,
  md: 4,
  lg: 6,
  pill: 999,
  targetMin: 44,
};

export const motion = {
  durPress: 120,
  durReveal: 180,
  durNav: 220,
  durStream: 60,
  durBeat: 420,
};

// Hard offset "print misregistration" shadows — no blur, per guidelines/depth-misregistration.
// iOS honors shadowOffset/shadowRadius directly; Android only gets elevation (a soft
// approximation), which is the best cross-platform tradeoff without a native shadow lib.
export function hardShadow(color: string, distance: 2 | 4 = 2) {
  return {
    shadowColor: color,
    shadowOffset: { width: distance, height: distance },
    shadowOpacity: 1,
    shadowRadius: 0,
    elevation: distance,
  } as const;
}
