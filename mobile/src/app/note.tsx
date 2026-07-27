import React, { useState } from 'react';
import { Pressable, ScrollView, Text, TextStyle, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Palette } from '@/theme/tokens';
import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { useQuickSwitcher } from '@/components/nav/QuickSwitcherContext';
import { AITutorChat } from '@/components/note/AITutorChat';
import { ReportSheet } from '@/components/report/ReportSheet';

type TermState = 'solid' | 'fading' | 'shaky';
type TopicStatus = 'ready' | 'synthesizing' | 'empty';

interface Topic {
  name: string;
  status: TopicStatus;
}

interface SheetSelection {
  concept: string;
  state: TermState;
}

interface StageEntry {
  name: string;
  state: TermState;
  where: string;
  why: string;
}

const TOPICS: Topic[] = [
  { name: 'Cellular Respiration', status: 'ready' },
  { name: 'Photosynthesis', status: 'synthesizing' },
  { name: 'Enzyme Kinetics', status: 'empty' },
];

const STAGE_ENTRIES: StageEntry[] = [
  { name: 'Glycolysis', state: 'solid', where: 'Cytoplasm · no oxygen needed', why: 'Splits glucose into two pyruvate — the entry point every downstream stage assumes is already done.' },
  { name: 'Krebs cycle', state: 'fading', where: 'Mitochondrial matrix', why: 'Strips carbons from pyruvate, banking electrons onto carriers (NADH, FADH₂) for the next stage.' },
  { name: 'Electron transport chain', state: 'shaky', where: 'Inner mitochondrial membrane', why: 'Uses those carriers to pump protons and drive most of the cell’s ATP synthesis.' },
];

const TABLE_ROWS: string[][] = [
  ['', 'Aerobic', 'Anaerobic'],
  ['Net ATP', '~30–32', '2'],
  ['Byproduct', 'CO₂ + H₂O', 'Lactate / ethanol'],
  ['O₂ required', 'Yes', 'No'],
];

const SYNTH_BAR_WIDTHS = [92, 78, 85, 60];

function stateStyles(c: Palette): Record<TermState, TextStyle> {
  return {
    solid: { color: c.stateSolid, fontWeight: '600', textDecorationLine: 'underline', textDecorationStyle: 'solid', textDecorationColor: c.stateSolid },
    fading: { color: c.stateFading, textDecorationLine: 'underline', textDecorationStyle: 'dashed', textDecorationColor: c.stateFading },
    shaky: { color: c.stateShaky, textDecorationLine: 'underline', textDecorationStyle: 'dotted', textDecorationColor: c.stateShaky },
  };
}

function stateLabel(state: TermState): string {
  return { solid: 'Solid', fading: 'Fading', shaky: 'Shaky' }[state];
}

function stateColor(c: Palette, state: TermState): string {
  return { solid: c.stateSolid, fading: c.stateFading, shaky: c.stateShaky }[state];
}

interface TermProps {
  state: TermState;
  children: string;
  onLaunch: (concept: string, state: TermState) => void;
}

function Term({ state, children, onLaunch }: TermProps) {
  const { c } = useTheme();
  return (
    <Text onPress={() => onLaunch(children, state)} style={[stateStyles(c)[state], { paddingVertical: 2 }]}>
      {children}
    </Text>
  );
}

function Rule({ label }: { label?: string }) {
  const { c, font, size, space, trackingUtility } = useTheme();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: space[6], marginBottom: space[4] }}>
      <View style={{ flex: label ? 0 : 1, width: label ? 16 : undefined, borderTopWidth: 1, borderTopColor: c.paperEdge }} />
      {label ? (
        <Text style={{ fontFamily: font.utility, fontSize: size.caption, letterSpacing: trackingUtility(size.caption), textTransform: 'uppercase', color: c.inkTertiary }}>
          {label}
        </Text>
      ) : null}
      <View style={{ flex: 1, borderTopWidth: 1, borderTopColor: c.paperEdge }} />
    </View>
  );
}

function PagerButton({ dir, onPress }: { dir: 'prev' | 'next'; onPress: () => void }) {
  const { c, radius } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityLabel={dir === 'prev' ? 'Previous topic' : 'Next topic'}
      hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
      style={{ width: 36, height: 36, flexShrink: 0, borderWidth: 1, borderColor: c.paperEdge, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' }}
    >
      <Text style={{ color: c.inkSecondary, fontSize: 16 }}>{dir === 'prev' ? '‹' : '›'}</Text>
    </Pressable>
  );
}

function TrustLink({ label, color, onPress }: { label: string; color: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={{ minHeight: 44, justifyContent: 'center' }}>
      <Text style={{ color, textDecorationLine: 'underline', fontSize: 13 }}>{label}</Text>
    </Pressable>
  );
}

export default function NoteScreen() {
  const { c, font, size, space, radius, trackingUtility } = useTheme();
  const { openSwitcher } = useQuickSwitcher();
  const [topicIndex, setTopicIndex] = useState(0);
  const [sheet, setSheet] = useState<SheetSelection | null>(null);
  const [showProvenance, setShowProvenance] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [showTutor, setShowTutor] = useState(false);

  const launchTerm = (concept: string, state: TermState) => setSheet({ concept, state });
  const topic = TOPICS[topicIndex];
  const cycle = (delta: number) => setTopicIndex((i) => (i + delta + TOPICS.length) % TOPICS.length);

  const startRetrieval = () => {
    if (!sheet) return;
    const { concept, state } = sheet;
    setSheet(null);
    router.push({ pathname: '/retrieval', params: { concept, conceptState: state } });
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
        <View style={{ padding: 20, paddingTop: 18, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: c.paperEdge }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
            <Text style={{ fontFamily: font.utility, fontSize: size.caption, letterSpacing: trackingUtility(size.caption), textTransform: 'uppercase', color: c.inkTertiary }}>
              Biology · Cell Biology
            </Text>
            <Pressable
              onPress={openSwitcher}
              accessibilityLabel="Switch"
              style={{ width: 44, height: 44, borderWidth: 1, borderColor: c.paperEdge, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}
            >
              <Text style={{ color: c.ink, fontSize: 16 }}>⌕</Text>
            </Pressable>
          </View>

          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <PagerButton dir="prev" onPress={() => cycle(-1)} />
            <Text style={{ flex: 1, fontFamily: font.display, fontSize: size.display2, lineHeight: size.display2 * 1.15, textAlign: 'center', color: c.ink }}>
              {topic.name}
            </Text>
            <PagerButton dir="next" onPress={() => cycle(1)} />
          </View>

          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 6, marginTop: 8 }}>
            {TOPICS.map((t, i) => (
              <View key={t.name} style={{ width: 5, height: 5, borderRadius: 2.5, backgroundColor: i === topicIndex ? c.ink : c.paperEdge }} />
            ))}
          </View>

          {topic.status === 'ready' && (
            <View style={{ marginTop: 10, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: c.confirm }} />
              <Text style={{ fontFamily: font.utility, fontSize: size.utility, color: c.confirm }}>
                Updated — Ada added the electron transport chain section
              </Text>
            </View>
          )}
        </View>

        <View style={{ flexDirection: 'row', gap: 10, paddingHorizontal: 20, paddingTop: 14 }}>
          <Button
            label="Ask the tutor"
            variant="secondary"
            icon={<Text style={{ color: c.ink }}>◎</Text>}
            onPress={() => setShowTutor(true)}
            style={{ flex: 1 }}
          />
          <Button
            label="Listen"
            variant="secondary"
            icon={<Text style={{ color: c.ink }}>♫</Text>}
            onPress={() => router.push('/listen')}
            style={{ flex: 1 }}
          />
        </View>

        <View style={{ paddingHorizontal: 20 }}>
          {topic.status === 'empty' ? (
            <View style={{ paddingVertical: 48, alignItems: 'center', gap: 12 }}>
              <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink }}>Nothing here yet</Text>
              <Text style={{ color: c.inkSecondary, fontSize: size.bodySm, maxWidth: 260, textAlign: 'center' }}>
                This topic is scaffolded but has no material. Add something to get a note started.
              </Text>
              <Button label="Add material" variant="text" onPress={() => router.push('/capture')} />
            </View>
          ) : topic.status === 'synthesizing' ? (
            <View style={{ paddingVertical: 32, gap: 14 }}>
              <Text style={{ fontFamily: font.utility, fontSize: size.utility, letterSpacing: trackingUtility(size.utility), textTransform: 'uppercase', color: c.stateFading }}>
                Synthesizing — writing itself in
              </Text>
              {SYNTH_BAR_WIDTHS.map((w, i) => (
                <View key={i} style={{ height: 14, width: `${w}%`, backgroundColor: c.paperRecessed, borderRadius: radius.sm }} />
              ))}
            </View>
          ) : (
            <>
              <Text style={{ fontSize: size.body, lineHeight: size.body * 1.55, color: c.ink, marginVertical: 18 }}>
                Cells release the energy stored in glucose in three connected stages.{' '}
                <Term state="solid" onLaunch={launchTerm}>Glycolysis</Term>
                {' happens first and needs no oxygen; its output feeds the '}
                <Term state="fading" onLaunch={launchTerm}>Krebs cycle</Term>
                {', which in turn hands electrons to the '}
                <Term state="shaky" onLaunch={launchTerm}>electron transport chain</Term>
                {' — the stage that produces the bulk of usable energy.'}
              </Text>

              <Rule label="The three stages" />
              <View style={{ gap: 14 }}>
                {STAGE_ENTRIES.map((e) => (
                  <View key={e.name} style={{ gap: 2 }}>
                    <Text style={{ fontWeight: '600' }}>
                      <Term state={e.state} onLaunch={launchTerm}>{e.name}</Term>
                    </Text>
                    <Text style={{ fontFamily: font.utility, fontSize: size.utility, letterSpacing: trackingUtility(size.utility), textTransform: 'uppercase', color: c.inkTertiary }}>
                      {e.where}
                    </Text>
                    <Text style={{ fontSize: size.bodySm, color: c.inkSecondary }}>{e.why}</Text>
                  </View>
                ))}
              </View>

              <Rule label="Worked example" />
              <View style={{ backgroundColor: c.paperRecessed, borderRadius: radius.lg, padding: 16, paddingHorizontal: 18, gap: 10 }}>
                <Text style={{ fontWeight: '600', color: c.ink }}>Net ATP yield from one glucose molecule?</Text>
                <View style={{ gap: 8 }}>
                  <Text style={{ fontSize: size.bodySm, color: c.ink }}>
                    {'1. '}<Term state="solid" onLaunch={launchTerm}>Glycolysis</Term>{' nets 2 ATP (substrate-level).'}
                  </Text>
                  <Text style={{ fontSize: size.bodySm, color: c.ink }}>
                    {'2. '}<Term state="fading" onLaunch={launchTerm}>Krebs cycle</Term>{' nets 2 ATP directly, plus electron carriers.'}
                  </Text>
                  <Text style={{ fontSize: size.bodySm, color: c.ink }}>
                    {'3. '}<Term state="shaky" onLaunch={launchTerm}>Electron transport chain</Term>{' converts those carriers into roughly 28–30 ATP.'}
                  </Text>
                  <Text style={{ fontSize: size.bodySm, fontWeight: '600', color: c.ink }}>4. Total: about 30–32 ATP per glucose.</Text>
                </View>
              </View>

              <Rule label="Rendered math" />
              <Text style={{ fontSize: size.body, color: c.ink, marginBottom: 18 }}>
                The free energy released,{' '}
                <Text style={{ fontFamily: font.math }}>ΔG = ΔH − TΔS</Text>
                {', is what the ETC captures as a proton gradient.'}
              </Text>

              <Rule label="Aerobic vs anaerobic" />
              <View style={{ marginBottom: 18 }}>
                {TABLE_ROWS.map((row, ri) => (
                  <View key={ri} style={{ flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: ri === 0 ? c.ink : c.paperEdge }}>
                    {row.map((cell, ci) => (
                      <Text
                        key={ci}
                        style={{
                          flex: 1,
                          textAlign: 'left',
                          paddingVertical: 8,
                          paddingHorizontal: 6,
                          fontSize: size.bodySm,
                          fontWeight: ri === 0 ? '600' : '400',
                          color: ri === 0 || ci === 0 ? c.ink : c.inkSecondary,
                        }}
                      >
                        {cell}
                      </Text>
                    ))}
                  </View>
                ))}
              </View>

              <View style={{ flexDirection: 'row', gap: 18, flexWrap: 'wrap', marginVertical: 4, marginBottom: 20 }}>
                <TrustLink label="Says who?" color={c.confirm} onPress={() => setShowProvenance(true)} />
                <TrustLink label="Read the original" color={c.confirm} onPress={() => router.push('/source')} />
                <TrustLink label="Report" color={c.inkTertiary} onPress={() => setShowReport(true)} />
              </View>
              <Text style={{ fontSize: size.bodySm, color: c.inkTertiary, paddingBottom: 8 }}>6 classmates built this note</Text>
            </>
          )}
        </View>
      </ScrollView>

      {sheet && (
        <RetrievalSheet concept={sheet.concept} state={sheet.state} onClose={() => setSheet(null)} onStart={startRetrieval} />
      )}

      <Sheet open={showProvenance} onClose={() => setShowProvenance(false)} title="Says who?">
        <Text style={{ color: c.inkSecondary, fontSize: size.body }}>
          This line draws on Ch. 6 of the assigned reading, plus lecture audio from Sept 14, corroborated across both.
        </Text>
      </Sheet>

      {showReport && <ReportSheet onClose={() => setShowReport(false)} />}

      {showTutor && (
        <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: c.paper, zIndex: 45 }}>
          <AITutorChat onBack={() => setShowTutor(false)} scope={topic.name} />
        </View>
      )}
    </SafeAreaView>
  );
}

function RetrievalSheet({ concept, state, onClose, onStart }: { concept: string; state: TermState; onClose: () => void; onStart: () => void }) {
  const { c, font, size } = useTheme();
  const label = stateLabel(state);
  const color = stateColor(c, state);

  return (
    <Sheet open onClose={onClose} title={`Retrieve: ${concept}`}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: color }} />
        <Text style={{ fontFamily: font.utility, fontSize: size.utility, textTransform: 'uppercase', color }}>
          {label} — worth a quick check
        </Text>
      </View>
      <Text style={{ marginBottom: 18, fontSize: size.body, color: c.ink }}>
        {`In your own words: what does ${concept} actually do, and what does it hand off to the next stage?`}
      </Text>
      <Button label="Start retrieval" onPress={onStart} style={{ width: '100%' }} />
      <Button label="Back to reading" variant="text" onPress={onClose} style={{ width: '100%', marginTop: 10 }} />
    </Sheet>
  );
}
