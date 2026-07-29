import React from 'react';
import { ScrollView, Text, View } from 'react-native';
import MathJax from 'react-native-mathjax-svg';
import { useTheme } from '@/theme/ThemeProvider';

// A display equation rendered as real MathJax SVG (via react-native-svg — no WebView, no
// fonts, offline). Wide equations scroll horizontally rather than overflowing the page.

function MathSvg({ latex }: { latex: string }) {
  const { c, size } = useTheme();
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={{ alignItems: 'center', paddingVertical: 8, paddingHorizontal: 4 }}
      style={{ marginVertical: 8 }}
    >
      <MathJax fontSize={size.body} color={c.ink}>
        {latex}
      </MathJax>
    </ScrollView>
  );
}

interface Props {
  latex: string;
}

interface BoundaryState {
  failed: boolean;
}

export class MathBlock extends React.Component<Props, BoundaryState> {
  state: BoundaryState = { failed: false };

  static getDerivedStateFromError(): BoundaryState {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return <RawMath latex={this.props.latex} />;
    }
    return <MathSvg latex={this.props.latex} />;
  }
}

function RawMath({ latex }: Props) {
  const { c, font, size } = useTheme();
  return (
    <View style={{ backgroundColor: c.paperRecessed, borderRadius: 8, padding: 12, marginVertical: 8 }}>
      <Text style={{ fontFamily: font.math, fontSize: size.bodySm, color: c.ink }}>{latex}</Text>
    </View>
  );
}
