import React from 'react';
import { Text, TextStyle, View } from 'react-native';
import { MathBlock } from '@/components/note/MathBlock';
import { convertInlineMath, splitNoteSegments } from '@/components/note/latex';

interface Props {
  content: string;
  textStyle?: TextStyle;
  gap?: number;
}

// Render a string that may mix prose, inline math ($…$) and display math ($$…$$) — reuses the
// note's math pipeline (MathBlock SVG for display, Unicode for inline). Not full markdown:
// STEM prompts/solutions are prose + equations, which is exactly what this covers.
export function MathText({ content, textStyle, gap = 4 }: Props) {
  const segments = splitNoteSegments(content);
  return (
    <View style={{ gap }}>
      {segments.map((seg, i) =>
        seg.type === 'math' ? (
          <MathBlock key={i} latex={seg.content} />
        ) : (
          <Text key={i} style={textStyle}>
            {convertInlineMath(seg.content).trim()}
          </Text>
        ),
      )}
    </View>
  );
}
