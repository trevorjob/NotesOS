import React, { useEffect, useState } from 'react';
import { Pressable, Text, TextStyle, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Chip } from '@/components/ui/Chip';
import { Sheet } from '@/components/ui/Sheet';
import { Textarea } from '@/components/ui/Textarea';
import type { ConceptState } from '@/components/ui/StateBadge';

type ModeId = 'quiz' | 'pretest' | 'ramble' | 'teach' | 'recap' | 'dump' | 'test';
type ModeShape = 'posed' | 'open' | 'sequence';

interface ModeDef {
  id: ModeId;
  label: string;
  blurb: string;
  shape: ModeShape;
  confidence?: boolean;
  scope?: 'concept' | 'session' | 'topic';
}

const MODES: ModeDef[] = [
  { id: 'quiz', label: 'Quiz', blurb: 'A posed question — multiple choice or short answer.', shape: 'posed', confidence: true },
  { id: 'pretest', label: 'Pretest', blurb: 'Answer before you’ve studied — a guess is fine, it primes learning.', shape: 'posed', confidence: true },
  { id: 'ramble', label: 'Ramble', blurb: 'Say or write everything you understand about this concept — no cues.', shape: 'open', scope: 'concept' },
  { id: 'teach', label: 'Teach it', blurb: 'Explain it like you’re teaching a classmate who’s never seen it.', shape: 'open', scope: 'concept' },
  { id: 'recap', label: 'Recap', blurb: 'Free-recall what you remember from your last study session.', shape: 'open', scope: 'session' },
  { id: 'dump', label: 'Brain dump', blurb: 'Everything you know about the whole topic, uncued.', shape: 'open', scope: 'topic' },
  { id: 'test', label: 'Timed test', blurb: 'A multi-question exam, against the clock.', shape: 'sequence' },
];

const MODE_IDS = MODES.map((m) => m.id);
const isModeId = (v: string | undefined): v is ModeId => !!v && (MODE_IDS as string[]).includes(v);

const OPTIONS = ['Glycolysis', 'Krebs cycle', 'Electron transport chain', 'Oxidative phosphorylation'];
const PRETEST_OPTIONS = ['Most of the cell’s ATP', 'Glucose', 'Oxygen', 'DNA'];
const CORRECT = 'Glycolysis';

interface ConfLevel {
  v: number;
  label: string;
}
const CONF_LEVELS: ConfLevel[] = [
  { v: 0.25, label: 'Guessing' },
  { v: 0.6, label: 'Fairly sure' },
  { v: 0.9, label: 'Certain' },
];

interface TestQuestion {
  q: string;
  options: string[];
  correct: string;
}
const TEST_QUESTIONS: TestQuestion[] = [
  { q: 'Which stage nets ATP directly, without needing oxygen?', options: OPTIONS, correct: CORRECT },
  { q: 'Where does the Krebs cycle take place?', options: ['Mitochondrial matrix', 'Cytoplasm', 'Nucleus', 'Inner membrane'], correct: 'Mitochondrial matrix' },
  { q: 'What is the final electron acceptor in the electron transport chain?', options: ['Oxygen', 'Glucose', 'Pyruvate', 'ATP'], correct: 'Oxygen' },
];

type RecapResult = 'nailed' | 'partial' | 'missed';
interface RecapConceptEntry {
  name: string;
  result: RecapResult;
}
const RECAP_CONCEPTS: RecapConceptEntry[] = [
  { name: 'Glycolysis', result: 'nailed' },
  { name: 'Krebs cycle', result: 'partial' },
  { name: 'Electron transport chain', result: 'missed' },
];
const RESULT_LABEL: Record<RecapResult, string> = { nailed: 'Nailed it', partial: 'Partial', missed: 'Missed' };

type AnswerTab = 'typed' | 'voice' | 'photo';
type PhotoStage = 'none' | 'captured' | 'confirmed';
type VoiceInputStage = 'idle' | 'recording' | 'captured';
type Stage = 'challenge' | 'confidence' | 'answer' | 'reveal' | 'prompt' | 'grading';

interface TestConfig {
  count?: number;
  type?: string;
  topics?: string[];
}

type Theme = ReturnType<typeof useTheme>;

function labelStyle(theme: Theme, color?: string): TextStyle {
  return {
    fontFamily: theme.font.utility,
    fontSize: theme.size.utility,
    letterSpacing: theme.trackingUtility(theme.size.utility),
    textTransform: 'uppercase',
    color: color ?? theme.c.inkTertiary,
  };
}

function getOpenPrompt(mode: ModeId, displayConcept: string, topic: string): string | undefined {
  switch (mode) {
    case 'ramble':
      return `Tell me everything you understand about ${displayConcept.toLowerCase()} — go until you run out.`;
    case 'teach':
      return `Explain ${displayConcept.toLowerCase()} like you’re teaching a classmate who’s never seen it.`;
    case 'recap':
      return 'What do you remember from your last study session? One free response — no cues.';
    case 'dump':
      return `Everything you know about ${topic} — the whole topic, uncued.`;
    default:
      return undefined;
  }
}

interface ConceptReveal {
  verdict: string;
  covered: string[];
  missing: string[];
}

function getRevealConcept(mode: ModeId): ConceptReveal | undefined {
  switch (mode) {
    case 'ramble':
      return {
        verdict: 'You covered the big picture but skipped two things worth naming.',
        covered: ['Location: inner mitochondrial membrane', 'Produces most of the cell’s ATP'],
        missing: ['Role of oxygen as final electron acceptor', 'Chemiosmosis / proton gradient'],
      };
    case 'teach':
      return {
        verdict: 'Clear delivery. One real gap in the explanation.',
        covered: ['Correct sequence of stages', 'Clear, classmate-friendly language'],
        missing: ['Didn’t explain why protons build a gradient'],
      };
    default:
      return undefined;
  }
}

interface ModePickerProps {
  open: boolean;
  onPick: (id: ModeId) => void;
  onClose: () => void;
}

function ModePicker({ open, onPick, onClose }: ModePickerProps) {
  const theme = useTheme();
  const { c } = theme;
  return (
    <Sheet open={open} onClose={onClose} title="Choose how to review">
      <View style={{ gap: 8 }}>
        {MODES.map((m) => (
          <Pressable
            key={m.id}
            onPress={() => onPick(m.id)}
            style={{
              minHeight: 44,
              padding: 14,
              borderWidth: 1,
              borderColor: c.paperEdge,
              borderRadius: theme.radius.md,
              backgroundColor: c.paper,
              gap: 4,
            }}
          >
            <Text style={{ fontFamily: theme.font.bodySemibold, fontSize: 16, color: c.ink }}>{m.label}</Text>
            <Text style={{ fontSize: theme.size.bodySm, color: c.inkSecondary }}>{m.blurb}</Text>
          </Pressable>
        ))}
      </View>
    </Sheet>
  );
}

interface AnswerInputProps {
  allow: AnswerTab[];
  tab: AnswerTab;
  setTab: (t: AnswerTab) => void;
  text: string;
  setText: (t: string) => void;
  photoStage: PhotoStage;
  setPhotoStage: (s: PhotoStage) => void;
  voiceStage: VoiceInputStage;
  setVoiceStage: (s: VoiceInputStage) => void;
}

const TAB_LABEL: Record<AnswerTab, string> = { typed: 'Type', voice: 'Voice', photo: 'Photo' };

function AnswerInput({ allow, tab, setTab, text, setText, photoStage, setPhotoStage, voiceStage, setVoiceStage }: AnswerInputProps) {
  const theme = useTheme();
  const { c } = theme;

  return (
    <View style={{ gap: 10 }}>
      {allow.length > 1 && (
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {allow.map((a) => (
            <Chip key={a} label={TAB_LABEL[a]} selected={tab === a} onPress={() => setTab(a)} />
          ))}
        </View>
      )}

      {tab === 'typed' && <Textarea rows={4} value={text} onChangeText={setText} placeholder="Type your answer…" />}

      {tab === 'voice' && (
        <View style={{ gap: 10, alignItems: 'center', paddingVertical: 20 }}>
          <View
            style={{
              width: 72,
              height: 72,
              borderRadius: 36,
              borderWidth: 3,
              borderColor: voiceStage === 'recording' ? c.confirm : c.paperEdge,
              justifyContent: 'center',
              alignItems: 'center',
            }}
          >
            <Text style={labelStyle(theme)}>{voiceStage === 'idle' ? 'Ready' : voiceStage === 'recording' ? 'Rec…' : 'Captured'}</Text>
          </View>
          {voiceStage !== 'captured' && (
            <Pressable
              onPress={() => setVoiceStage(voiceStage === 'recording' ? 'captured' : 'recording')}
              style={{ minHeight: 44, borderWidth: 1, borderColor: c.paperEdge, borderRadius: theme.radius.md, paddingHorizontal: 18, paddingVertical: 10, justifyContent: 'center', alignItems: 'center' }}
            >
              <Text style={{ fontSize: 15, color: c.ink }}>{voiceStage === 'recording' ? 'Stop' : 'Start recording'}</Text>
            </Pressable>
          )}
          {voiceStage === 'captured' && (
            <Pressable onPress={() => setVoiceStage('idle')} style={{ minHeight: 44, justifyContent: 'center' }}>
              <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: 14 }}>Re-record</Text>
            </Pressable>
          )}
        </View>
      )}

      {tab === 'photo' && (
        <View style={{ gap: 10 }}>
          {photoStage === 'none' && (
            <Pressable
              onPress={() => setPhotoStage('captured')}
              style={{
                minHeight: 44,
                borderWidth: 1,
                borderStyle: 'dashed',
                borderColor: c.paperEdge,
                backgroundColor: c.paperRecessed,
                borderRadius: theme.radius.md,
                paddingVertical: 18,
                justifyContent: 'center',
                alignItems: 'center',
              }}
            >
              <Text style={{ fontSize: 15, color: c.ink }}>Snap a photo of your written work</Text>
            </Pressable>
          )}
          {photoStage !== 'none' && (
            <View style={{ gap: 10 }}>
              <View
                style={{
                  height: 100,
                  borderWidth: 1,
                  borderColor: c.paperEdge,
                  borderRadius: theme.radius.md,
                  backgroundColor: c.paperRecessed,
                  justifyContent: 'center',
                  alignItems: 'center',
                }}
              >
                <Text style={{ color: c.inkTertiary, fontSize: 13 }}>photo of your answer</Text>
              </View>
              {photoStage === 'captured' && (
                <Text style={{ fontSize: theme.size.bodySm }}>
                  <Text style={labelStyle(theme)}>Transcribed: </Text>
                  <Text style={{ color: c.ink }}>looks legible — confirm it’s right</Text>
                </Text>
              )}
              <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
                {photoStage === 'captured' && (
                  <Button label="Looks right" onPress={() => setPhotoStage('confirmed')} style={{ flex: 1, paddingVertical: 10, paddingHorizontal: 0 }} />
                )}
                <Pressable onPress={() => setPhotoStage('none')} style={{ minHeight: 44, justifyContent: 'center' }}>
                  <Text style={{ color: c.inkSecondary, fontSize: 14 }}>Retake</Text>
                </Pressable>
              </View>
            </View>
          )}
        </View>
      )}
    </View>
  );
}

interface ModeHeaderProps {
  mode: ModeId;
  concept: string;
  onChangeMode: () => void;
}

function ModeHeader({ mode, concept, onChangeMode }: ModeHeaderProps) {
  const theme = useTheme();
  const { c } = theme;
  const m = MODES.find((x) => x.id === mode) ?? MODES[0];
  return (
    <View style={{ paddingHorizontal: 20, paddingTop: 18, paddingBottom: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
      <Text style={labelStyle(theme)}>{`${m.label} · ${concept}`}</Text>
      <Pressable onPress={onChangeMode} style={{ minHeight: 44, justifyContent: 'center' }}>
        <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: theme.size.caption }}>Change mode</Text>
      </Pressable>
    </View>
  );
}

interface TestSequenceProps {
  config?: TestConfig;
  onDone: () => void;
  onBackToNote: () => void;
}

function TestSequence({ config, onDone, onBackToNote }: TestSequenceProps) {
  const theme = useTheme();
  const { c } = theme;
  const questions = TEST_QUESTIONS.slice(0, Math.max(1, Math.min(TEST_QUESTIONS.length, config?.count || TEST_QUESTIONS.length)));
  const [idx, setIdx] = useState(0);
  const [score, setScore] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const done = idx >= questions.length;
  const q = !done ? questions[idx] : null;

  const choose = (opt: string) => {
    setPicked(opt);
    setTimeout(() => {
      if (q && opt === q.correct) setScore((s) => s + 1);
      setPicked(null);
      setIdx((i) => i + 1);
    }, 450);
  };

  const mmss = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, '0')}`;

  return (
    <View style={{ flex: 1 }}>
      <View style={{ paddingHorizontal: 20, paddingTop: 18, paddingBottom: 10, flexDirection: 'row', justifyContent: 'space-between' }}>
        <Text style={labelStyle(theme)}>{done ? 'Timed test · done' : `Question ${idx + 1} of ${questions.length}`}</Text>
        <Text style={labelStyle(theme)}>{mmss}</Text>
      </View>
      <View style={{ flex: 1, paddingHorizontal: 20, gap: 18, justifyContent: 'center' }}>
        {done ? (
          <>
            <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display2, color: c.ink }}>{`Score: ${score} / ${questions.length}`}</Text>
            <Text style={{ color: c.inkSecondary, fontSize: theme.size.bodySm }}>{`Finished in ${mmss}.`}</Text>
            <Button label="Continue" onPress={onDone} />
          </>
        ) : (
          q && (
            <>
              <Text style={{ fontFamily: theme.font.display, fontWeight: '500', fontSize: theme.size.display3, lineHeight: theme.size.display3 * theme.lineHeight.display, color: c.ink }}>
                {q.q}
              </Text>
              <View style={{ gap: 10 }}>
                {q.options.map((opt) => {
                  const isPicked = picked === opt;
                  const bg = isPicked ? (opt === q.correct ? c.confirm : c.paperRecessed) : c.paper;
                  const color = isPicked && opt === q.correct ? c.paper : c.ink;
                  return (
                    <Pressable
                      key={opt}
                      disabled={picked !== null}
                      onPress={() => choose(opt)}
                      style={{ minHeight: 44, paddingHorizontal: 14, paddingVertical: 12, borderRadius: theme.radius.md, borderWidth: 1, borderColor: c.paperEdge, backgroundColor: bg, justifyContent: 'center' }}
                    >
                      <Text style={{ fontFamily: theme.font.body, fontSize: 16, color }}>{opt}</Text>
                    </Pressable>
                  );
                })}
              </View>
            </>
          )
        )}
      </View>
      <Pressable onPress={onBackToNote} style={{ marginHorizontal: 20, marginBottom: 20, minHeight: 44, justifyContent: 'center' }}>
        <Text style={{ color: c.inkSecondary, fontSize: 14 }}>← Exit test</Text>
      </Pressable>
    </View>
  );
}

export default function RetrievalScreen() {
  const theme = useTheme();
  const { c } = theme;
  const params = useLocalSearchParams<{ concept?: string; conceptState?: string; mode?: string; count?: string; type?: string; topics?: string }>();

  const topic = 'Cellular Respiration';
  const displayConcept = params.concept || 'Electron transport chain';
  const rawConceptState = params.conceptState;
  const conceptState: ConceptState | undefined =
    rawConceptState === 'solid' || rawConceptState === 'fading' || rawConceptState === 'shaky' ? rawConceptState : undefined;

  const testConfig: TestConfig = {
    count: params.count && !Number.isNaN(Number(params.count)) ? Number(params.count) : undefined,
    type: params.type,
    topics: params.topics ? params.topics.split(',') : undefined,
  };

  const [mode, setMode] = useState<ModeId>(isModeId(params.mode) ? params.mode : 'quiz');
  const [pickerOpen, setPickerOpen] = useState(false);
  const [stage, setStage] = useState<Stage>('challenge');
  const [confidence, setConfidence] = useState<ConfLevel | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [answerMode, setAnswerMode] = useState<'mcq' | 'freeform'>('mcq');
  const [tab, setTab] = useState<AnswerTab>('typed');
  const [text, setText] = useState('');
  const [photoStage, setPhotoStage] = useState<PhotoStage>('none');
  const [voiceStage, setVoiceStage] = useState<VoiceInputStage>('idle');
  const [dots, setDots] = useState(1);

  useEffect(() => {
    if (stage !== 'grading') return;
    const id = setInterval(() => setDots((d) => (d % 3) + 1), 350);
    const t = setTimeout(() => {
      setStage('reveal');
      clearInterval(id);
    }, 1500);
    return () => {
      clearInterval(id);
      clearTimeout(t);
    };
  }, [stage]);

  const onDone = () => router.back();
  const onBackToNote = () => router.back();
  const onVoice = (concept: string) => router.push({ pathname: '/voice', params: { concept } });

  const changeMode = (m: ModeId) => {
    setMode(m);
    setPickerOpen(false);
    setStage(m === 'quiz' || m === 'pretest' ? 'challenge' : 'prompt');
    setConfidence(null);
    setPicked(null);
    setAnswerMode('mcq');
    setTab('typed');
    setText('');
    setPhotoStage('none');
    setVoiceStage('idle');
  };

  if (mode === 'test') {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
        <TestSequence config={testConfig} onDone={onDone} onBackToNote={onBackToNote} />
      </SafeAreaView>
    );
  }

  const m = MODES.find((x) => x.id === mode) ?? MODES[0];
  const correct = picked === CORRECT;
  const isPretest = mode === 'pretest';
  const calibration =
    confidence == null
      ? null
      : correct && confidence.v >= 0.6
        ? 'Calibrated — you called that right.'
        : correct && confidence.v < 0.6
          ? 'You knew more than you thought — nice.'
          : !correct && confidence.v >= 0.6
            ? isPretest
              ? 'Overconfident, and that’s exactly what pretests catch.'
              : 'Overconfident here — worth a closer look, gently.'
            : 'Underconfident — you were closer than you guessed.';

  const canSubmitOpen = tab === 'typed' ? text.trim().length > 0 : tab === 'voice' ? voiceStage === 'captured' : photoStage === 'confirmed';

  const openPrompt = getOpenPrompt(mode, displayConcept, topic);
  const revealConcept = getRevealConcept(mode);

  const questionStyle: TextStyle = {
    fontFamily: theme.font.display,
    fontWeight: '500',
    fontSize: theme.size.display3,
    lineHeight: theme.size.display3 * theme.lineHeight.display,
    color: c.ink,
  };
  const optionButtonStyle = {
    minHeight: 44,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: c.paperEdge,
    backgroundColor: c.paper,
    justifyContent: 'center' as const,
  };
  const stateColor: Record<ConceptState, string> = { solid: c.stateSolid, fading: c.stateFading, shaky: c.stateShaky };
  const resultColor: Record<RecapResult, string> = { nailed: c.stateSolid, partial: c.stateFading, missed: c.stateShaky };

  const posedQuestion = isPretest
    ? `Before you’ve studied — what does ${displayConcept.toLowerCase()} actually produce?`
    : 'Which stage nets ATP directly, without needing oxygen?';

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      {stage !== 'grading' && (
        <ModeHeader
          mode={mode}
          concept={m.scope === 'topic' ? topic : m.scope === 'session' ? 'Last session' : displayConcept}
          onChangeMode={() => setPickerOpen(true)}
        />
      )}

      <View style={{ flex: 1, paddingHorizontal: 20, gap: 18, justifyContent: 'center' }}>
        {m.shape === 'posed' && stage !== 'reveal' && (
          <>
            {conceptState && <Text style={labelStyle(theme, stateColor[conceptState])}>{conceptState}</Text>}
            <Text style={questionStyle}>{posedQuestion}</Text>

            {stage === 'challenge' && <Button label="How sure are you?" onPress={() => setStage('confidence')} />}

            {stage === 'confidence' && (
              <View style={{ gap: 10 }}>
                {CONF_LEVELS.map((lvl) => (
                  <Pressable
                    key={lvl.label}
                    onPress={() => {
                      setConfidence(lvl);
                      setStage('answer');
                    }}
                    style={optionButtonStyle}
                  >
                    <Text style={{ fontFamily: theme.font.body, fontSize: 16, color: c.ink }}>{lvl.label}</Text>
                  </Pressable>
                ))}
              </View>
            )}

            {stage === 'answer' && answerMode === 'mcq' && (
              <>
                <Pressable onPress={() => onVoice(displayConcept)} style={{ minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' }}>
                  <Text style={{ color: c.inkTertiary, textDecorationLine: 'underline', fontSize: theme.size.caption }}>Answer by voice instead (preview)</Text>
                </Pressable>
                <View style={{ gap: 10 }}>
                  {(isPretest ? PRETEST_OPTIONS : OPTIONS).map((opt) => (
                    <Pressable
                      key={opt}
                      onPress={() => {
                        setPicked(opt);
                        setStage('reveal');
                      }}
                      style={optionButtonStyle}
                    >
                      <Text style={{ fontFamily: theme.font.body, fontSize: 16, color: c.ink }}>{opt}</Text>
                    </Pressable>
                  ))}
                </View>
                {!isPretest && (
                  <Pressable onPress={() => setAnswerMode('freeform')} style={{ minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' }}>
                    <Text style={{ color: c.inkTertiary, textDecorationLine: 'underline', fontSize: theme.size.caption }}>Prefer to answer by typing or photo instead?</Text>
                  </Pressable>
                )}
              </>
            )}

            {stage === 'answer' && answerMode === 'freeform' && (
              <>
                <AnswerInput
                  allow={['typed', 'photo']}
                  tab={tab === 'voice' ? 'typed' : tab}
                  setTab={setTab}
                  text={text}
                  setText={setText}
                  photoStage={photoStage}
                  setPhotoStage={setPhotoStage}
                  voiceStage={voiceStage}
                  setVoiceStage={setVoiceStage}
                />
                <Button
                  label="Submit"
                  disabled={!canSubmitOpen}
                  onPress={() => {
                    setPicked(CORRECT);
                    setStage('reveal');
                  }}
                />
              </>
            )}
          </>
        )}

        {m.shape === 'posed' && stage === 'reveal' && (
          <View style={{ gap: 14 }}>
            <Text style={questionStyle}>{posedQuestion}</Text>
            <View style={{ gap: 10 }}>
              {(isPretest ? PRETEST_OPTIONS : OPTIONS).map((opt) => {
                const isCorrectOpt = isPretest ? opt === 'Most of the cell’s ATP' : opt === CORRECT;
                const isPicked = picked === opt;
                const bg = isCorrectOpt ? c.confirm : isPicked && !isCorrectOpt ? c.paperRecessed : c.paper;
                const color = isCorrectOpt ? c.paper : c.ink;
                return (
                  <View
                    key={opt}
                    style={{ minHeight: 44, paddingHorizontal: 14, paddingVertical: 12, borderRadius: theme.radius.md, borderWidth: 1, borderColor: c.paperEdge, backgroundColor: bg, justifyContent: 'center' }}
                  >
                    <Text style={{ fontFamily: theme.font.body, fontSize: 16, color }}>{opt}</Text>
                  </View>
                );
              })}
            </View>
            <Text style={{ fontSize: theme.size.body, color: isPretest ? c.inkSecondary : correct ? c.confirm : c.inkSecondary }}>
              {isPretest ? 'Good to have a baseline — pretests aren’t scored against you.' : correct ? 'Correct.' : `Not quite — it's ${CORRECT}.`}
            </Text>
            {calibration && <Text style={labelStyle(theme)}>{calibration}</Text>}
            <Text style={{ fontSize: theme.size.bodySm, color: c.inkSecondary }}>
              Glycolysis nets 2 ATP through substrate-level phosphorylation, entirely in the cytoplasm — no oxygen required.
            </Text>
            <Button label="Continue" onPress={onDone} />
          </View>
        )}

        {m.shape === 'open' && stage === 'prompt' && (
          <>
            <Text style={questionStyle}>{openPrompt}</Text>
            <AnswerInput
              allow={['voice', 'typed', 'photo']}
              tab={tab}
              setTab={setTab}
              text={text}
              setText={setText}
              photoStage={photoStage}
              setPhotoStage={setPhotoStage}
              voiceStage={voiceStage}
              setVoiceStage={setVoiceStage}
            />
            <Button label="Submit" disabled={!canSubmitOpen} onPress={() => setStage('grading')} />
          </>
        )}

        {m.shape === 'open' && stage === 'grading' && (
          <Text style={{ textAlign: 'center', color: c.inkSecondary, fontSize: theme.size.body }}>{`Scoring your answer${'.'.repeat(dots)}`}</Text>
        )}

        {m.shape === 'open' && stage === 'reveal' && m.scope === 'concept' && revealConcept && (
          <View style={{ gap: 14 }}>
            <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display3, color: c.ink }}>{revealConcept.verdict}</Text>
            <View>
              <Text style={labelStyle(theme, c.confirm)}>Covered</Text>
              {revealConcept.covered.map((item, i) => (
                <Text key={i} style={{ fontSize: theme.size.bodySm, color: c.inkSecondary, marginTop: 6 }}>{`• ${item}`}</Text>
              ))}
            </View>
            <View>
              <Text style={labelStyle(theme, c.stateShaky)}>Still fuzzy on</Text>
              {revealConcept.missing.map((item, i) => (
                <Text key={i} style={{ fontSize: theme.size.bodySm, color: c.inkSecondary, marginTop: 6 }}>{`• ${item}`}</Text>
              ))}
            </View>
            <Button label="Continue" onPress={onDone} />
          </View>
        )}

        {m.shape === 'open' && stage === 'reveal' && m.scope !== 'concept' && (
          <View style={{ gap: 14 }}>
            <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display3, color: c.ink }}>
              Graded across the whole set — one response, per-concept results.
            </Text>
            <View style={{ gap: 10 }}>
              {RECAP_CONCEPTS.map((entry) => (
                <View key={entry.name} style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: c.paperEdge }}>
                  <Text style={{ color: c.ink, fontSize: theme.size.body }}>{entry.name}</Text>
                  <Text style={labelStyle(theme, resultColor[entry.result])}>{RESULT_LABEL[entry.result]}</Text>
                </View>
              ))}
            </View>
            <Button label="Continue" onPress={onDone} />
          </View>
        )}
      </View>

      {stage !== 'grading' && (
        <Pressable onPress={onBackToNote} style={{ marginHorizontal: 20, marginBottom: 20, minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ color: c.inkSecondary, fontSize: 14 }}>← Back to reading</Text>
        </Pressable>
      )}

      <ModePicker open={pickerOpen} onPick={changeMode} onClose={() => setPickerOpen(false)} />
    </SafeAreaView>
  );
}
