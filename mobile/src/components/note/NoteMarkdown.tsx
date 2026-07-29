import React from 'react';
import { Text, TextStyle, View } from 'react-native';
import { useMarkdown, type MarkedStyles, Renderer, type RendererInterface } from 'react-native-marked';
import { useTheme } from '@/theme/ThemeProvider';
import { Palette } from '@/theme/tokens';
import { ConceptMastery } from '@/lib/note';
import { masteryTextStyle } from '@/components/note/mastery';
import { MathBlock } from '@/components/note/MathBlock';
import { convertInlineMath, splitNoteSegments } from '@/components/note/latex';

// The note body is markdown (headings, lists, tables, fenced code, LaTeX $…$ — see
// knowledge_synthesizer). react-native-marked renders all but the LaTeX (passed through as
// text; math rendering is a tracked follow-up). Rendered via the useMarkdown hook, not the
// <Markdown> component, so it lives in the note's own ScrollView instead of a nested FlatList.
//
// The whole note is "lit by mastery": a custom renderer scans every text run for concept
// terms and wraps each in a tappable, mastery-coloured span (system-spec §4/§5). This is the
// note's point — the words themselves light up as you learn, not a separate glossary.

export interface ConceptIndex {
  regex: RegExp;
  lookup: Map<string, ConceptMastery>;
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Canonical form for matching: case-folded, whitespace collapsed. Both the lookup keys and
// each match are normalized through this, so "Electron  Transport" (wrapped / double-spaced)
// matches "electron transport". Morphological variants (plurals/tense) are NOT normalized —
// that needs stemming and risks over-matching; a known limitation.
function normalizeTerm(s: string): string {
  return s.replace(/\s+/g, ' ').trim().toLowerCase();
}

/** Build a case-insensitive, whitespace-tolerant matcher over the topic's tappable concept
 *  terms (longest first so multi-word terms win over their prefixes). Null when empty. */
export function buildConceptIndex(concepts: ConceptMastery[]): ConceptIndex | null {
  const lookup = new Map<string, ConceptMastery>();
  for (const concept of concepts) {
    const key = normalizeTerm(concept.term);
    if (concept.concept_id && key && !lookup.has(key)) lookup.set(key, concept);
  }
  if (lookup.size === 0) return null;
  const terms = [...lookup.values()]
    .map((concept) => concept.term.trim())
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);
  // Escape regex metachars, then let any whitespace run in the term match any whitespace run.
  const pattern = terms.map((t) => escapeRegExp(t).replace(/\s+/g, '\\s+')).join('|');
  const regex = new RegExp(`\\b(${pattern})\\b`, 'gi');
  return { regex, lookup };
}

function lightSpans(
  text: string,
  index: ConceptIndex,
  c: Palette,
  onLaunch: (concept: ConceptMastery) => void,
  keyPrefix: string
): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let last = 0;
  let i = 0;
  index.regex.lastIndex = 0;
  for (const match of text.matchAll(index.regex)) {
    const concept = index.lookup.get(normalizeTerm(match[0]));
    if (!concept || match.index === undefined) continue;
    if (match.index > last) out.push(text.slice(last, match.index));
    out.push(
      <Text key={`${keyPrefix}-${i++}`} onPress={() => onLaunch(concept)} style={masteryTextStyle(c, concept.state)}>
        {match[0]}
      </Text>
    );
    last = match.index + match[0].length;
  }
  if (out.length === 0) return [text];
  if (last < text.length) out.push(text.slice(last));
  return out;
}

// Override only text(): plain runs get scanned for concept terms; already-composed
// ReactNode[] (nested inline spans) pass through to the base renderer unchanged.
function makeRenderer(
  index: ConceptIndex | null,
  c: Palette,
  onLaunch: (concept: ConceptMastery) => void
): RendererInterface {
  const base = new Renderer();
  if (!index) return base;

  const originalText = base.text.bind(base);
  let key = 0;
  base.text = (content: string | React.ReactNode[], styles?: TextStyle): React.ReactNode => {
    if (typeof content !== 'string') return originalText(content, styles);
    key += 1;
    return (
      <Text key={`litblock-${key}`} selectable style={styles}>
        {lightSpans(content, index, c, onLaunch, `lit-${key}`)}
      </Text>
    );
  };
  return base;
}

function markedStyles(c: Palette, font: ReturnType<typeof useTheme>['font'], size: ReturnType<typeof useTheme>['size']): MarkedStyles {
  return {
    text: { color: c.ink, fontSize: size.body, lineHeight: size.body * 1.55 },
    paragraph: { marginVertical: 8 },
    strong: { fontWeight: '600', color: c.ink },
    em: { fontStyle: 'italic' },
    h1: { fontFamily: font.display, fontSize: size.display3, color: c.ink, marginTop: 16, marginBottom: 6 },
    h2: { fontFamily: font.display, fontSize: size.display3, color: c.ink, marginTop: 14, marginBottom: 6 },
    h3: { fontWeight: '600', fontSize: size.body, color: c.ink, marginTop: 12, marginBottom: 4 },
    li: { color: c.ink, fontSize: size.body, lineHeight: size.body * 1.5 },
    codespan: { fontFamily: font.math, color: c.ink, backgroundColor: c.paperRecessed },
    code: { backgroundColor: c.paperRecessed, borderRadius: 8, padding: 12 },
    blockquote: { borderLeftWidth: 3, borderLeftColor: c.paperEdge, paddingLeft: 12 },
    hr: { backgroundColor: c.paperEdge },
    table: { borderColor: c.paperEdge },
    tableCell: { borderColor: c.paperEdge },
    link: { color: c.confirm },
  };
}

function MarkdownNodes({ value, index, onLaunch }: Props) {
  const { c, font, size } = useTheme();
  const renderer = React.useMemo(() => makeRenderer(index, c, onLaunch), [index, c, onLaunch]);
  const elements = useMarkdown(value, {
    theme: { colors: { text: c.ink, code: c.ink, link: c.confirm, border: c.paperEdge } },
    styles: markedStyles(c, font, size),
    renderer,
  });
  return (
    <View>
      {elements.map((el, i) => (
        <React.Fragment key={i}>{el}</React.Fragment>
      ))}
    </View>
  );
}

// Split display math out (rendered as SVG), leaving inline math (converted to Unicode) in
// the markdown runs so it flows and stays lightable.
function NoteBody({ value, index, onLaunch }: Props) {
  const segments = React.useMemo(() => splitNoteSegments(value), [value]);
  return (
    <View>
      {segments.map((seg, i) =>
        seg.type === 'math' ? (
          <MathBlock key={`math-${i}`} latex={seg.content} />
        ) : (
          <MarkdownNodes key={`md-${i}`} value={convertInlineMath(seg.content)} index={index} onLaunch={onLaunch} />
        )
      )}
    </View>
  );
}

/** A plain (non-markdown) string with concept terms lit inline — used for key points. */
export function LitText({
  value,
  index,
  onLaunch,
  style,
}: {
  value: string;
  index: ConceptIndex | null;
  onLaunch: (concept: ConceptMastery) => void;
  style?: TextStyle;
}) {
  const { c } = useTheme();
  const text = convertInlineMath(value);
  if (!index) return <Text style={style}>{text}</Text>;
  return <Text style={style}>{lightSpans(text, index, c, onLaunch, 'kp')}</Text>;
}

interface Props {
  value: string;
  index: ConceptIndex | null;
  onLaunch: (concept: ConceptMastery) => void;
}

interface BoundaryState {
  failed: boolean;
}

// If the markdown lexer/renderer throws on some input, fall back to plain text rather than
// taking down the whole note screen.
export class NoteMarkdown extends React.Component<Props, BoundaryState> {
  state: BoundaryState = { failed: false };

  static getDerivedStateFromError(): BoundaryState {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return <PlainFallback value={this.props.value} />;
    }
    return <NoteBody {...this.props} />;
  }
}

function PlainFallback({ value }: { value: string }) {
  const { c, size } = useTheme();
  return <Text style={{ color: c.ink, fontSize: size.body, lineHeight: size.body * 1.55 }}>{value}</Text>;
}
