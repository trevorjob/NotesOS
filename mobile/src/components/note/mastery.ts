import { TextStyle } from 'react-native';
import { Palette } from '@/theme/tokens';
import { MasteryState } from '@/lib/note';

// How a concept term reads when lit inline in the note: solid glows (solid underline),
// fading dims (dashed), shaky is dotted+warm, new is a faint dotted hint (studied nothing
// yet, but still a live retrieval entry point). See system-spec §4/§5.
export function masteryTextStyle(c: Palette, state: MasteryState): TextStyle {
  switch (state) {
    case 'solid':
      return { color: c.stateSolid, fontWeight: '600', textDecorationLine: 'underline', textDecorationStyle: 'solid', textDecorationColor: c.stateSolid };
    case 'fading':
      return { color: c.stateFading, textDecorationLine: 'underline', textDecorationStyle: 'dashed', textDecorationColor: c.stateFading };
    case 'shaky':
      return { color: c.stateShaky, textDecorationLine: 'underline', textDecorationStyle: 'dotted', textDecorationColor: c.stateShaky };
    default:
      return { textDecorationLine: 'underline', textDecorationStyle: 'dotted', textDecorationColor: c.inkTertiary };
  }
}

export function stateLabel(state: MasteryState): string {
  return { new: 'Not started', solid: 'Solid', fading: 'Fading', shaky: 'Shaky' }[state];
}

export function stateColor(c: Palette, state: MasteryState): string {
  return { new: c.inkTertiary, solid: c.stateSolid, fading: c.stateFading, shaky: c.stateShaky }[state];
}
