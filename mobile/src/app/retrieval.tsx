import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, Text, TextStyle, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { isAxiosError } from 'axios';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { Textarea } from '@/components/ui/Textarea';
import { MathText } from '@/components/retrieval/MathText';
import { WrittenAnswer } from '@/components/retrieval/WrittenAnswer';
import { ConversationalBout } from '@/components/retrieval/ConversationalBout';
import {
  ConfLevel,
  CONF_LEVELS,
  SingleResult,
  gradeColor,
  labelStyle,
  readError,
} from '@/components/retrieval/retrievalShared';
import { takePhoto } from '@/lib/filePicker';
import type { ConceptState } from '@/components/ui/StateBadge';
import {
  AttemptResult,
  CalibrationLabel,
  FreeRecallChallenge,
  FreeRecallResult,
  ModeInfo,
  NextChallenge,
  RevealResult,
  SelfGrade,
  SessionSummary,
  TopicProfile,
  dumpAttempt,
  dumpNext,
  fetchModes,
  fetchSessionSummary,
  fetchTopicProfile,
  nextChallenge,
  recapAttempt,
  recapNext,
  revealSolution,
  submitAttempt,
  transcribePaper,
} from '@/lib/retrieval';

type ModeId = 'quiz' | 'pretest' | 'ramble' | 'teach' | 'recap' | 'dump';
type ModeShape = 'posed' | 'open' | 'freerecall';

interface ModeDef {
  id: ModeId;
  label: string;
  blurb: string;
  shape: ModeShape;
}

// Client-side copy for each backend mode. quiz/pretest/ramble/teach come from GET /modes
// (the engine registry); recap/dump are the free-recall siblings — topic-scoped surfaces
// that live outside the registry, always offered when we have a topic.
const MODES: ModeDef[] = [
  { id: 'quiz', label: 'Quiz', blurb: 'A posed question — multiple choice or short answer.', shape: 'posed' },
  { id: 'pretest', label: 'Pretest', blurb: 'Answer before you’ve studied — a guess is fine, it primes learning.', shape: 'posed' },
  { id: 'ramble', label: 'Ramble', blurb: 'Say everything you understand about this concept — no cues.', shape: 'open' },
  { id: 'teach', label: 'Teach it', blurb: 'Explain it like you’re teaching a classmate who’s never seen it.', shape: 'open' },
  { id: 'recap', label: 'Recap', blurb: 'Free-recall what you remember from your last study session.', shape: 'freerecall' },
  { id: 'dump', label: 'Brain dump', blurb: 'Everything you know about the whole topic, uncued.', shape: 'freerecall' },
];

const FREE_RECALL_IDS: ModeId[] = ['recap', 'dump'];
const MODE_BY_ID = new Map(MODES.map((m) => [m.id, m]));
const isModeId = (v: string | undefined): v is ModeId => !!v && MODE_BY_ID.has(v as ModeId);

// The subject profile's mode_mix keys the brain dump as "brain_dump", not "dump".
const affinityKey = (id: ModeId): string => (id === 'dump' ? 'brain_dump' : id);

const FAMILY_LABEL: Record<TopicProfile['subject_family'], string | null> = {
  STEM: 'this STEM topic',
  LANGUAGE: 'this language topic',
  HUMANITIES: 'this humanities topic',
  SOCIAL_SCIENCE: 'this social science topic',
  GENERAL: null,
};

// The four honest self-grade buttons for a worked STEM problem (system-spec §5).
const SELF_GRADES: { key: SelfGrade; label: string }[] = [
  { key: 'again', label: 'Blank / wrong approach' },
  { key: 'hard', label: 'Right method, slipped' },
  { key: 'good', label: 'Solved it' },
  { key: 'easy', label: 'Solved it cold' },
];

type Stage = 'loading' | 'error' | 'challenge' | 'confidence' | 'answer' | 'grading' | 'result' | 'close';

interface ModePickerProps {
  open: boolean;
  modes: ModeDef[];
  recommendedId?: ModeId;
  familyLabel?: string | null;
  onPick: (id: ModeId) => void;
  onClose: () => void;
}

// Context-worthy picker (retrieval-experience.md §6): modes are ordered best-fit-first for the
// topic's subject and the top one is badged — so the recommendation leads, it's not a flat list.
function ModePicker({ open, modes, recommendedId, familyLabel, onPick, onClose }: ModePickerProps) {
  const theme = useTheme();
  const { c } = theme;
  return (
    <Sheet open={open} onClose={onClose} title="Choose how to review">
      {familyLabel && (
        <Text style={[labelStyle(theme), { marginBottom: 10 }]}>{`Ranked for ${familyLabel}`}</Text>
      )}
      <View style={{ gap: 8 }}>
        {modes.map((m) => {
          const recommended = m.id === recommendedId;
          return (
            <Pressable
              key={m.id}
              onPress={() => onPick(m.id)}
              style={{
                minHeight: 44,
                padding: 14,
                borderWidth: recommended ? 1.5 : 1,
                borderColor: recommended ? c.confirm : c.paperEdge,
                borderRadius: theme.radius.md,
                backgroundColor: c.paper,
                gap: 4,
              }}
            >
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ fontFamily: theme.font.bodySemibold, fontSize: 16, color: c.ink }}>{m.label}</Text>
                {recommended && <Text style={labelStyle(theme, c.confirm)}>Best fit</Text>}
              </View>
              <Text style={{ fontSize: theme.size.bodySm, color: c.inkSecondary }}>{m.blurb}</Text>
            </Pressable>
          );
        })}
      </View>
    </Sheet>
  );
}

interface ModeHeaderProps {
  label: string;
  scopeLabel: string;
  onChangeMode: () => void;
}

function ModeHeader({ label, scopeLabel, onChangeMode }: ModeHeaderProps) {
  const theme = useTheme();
  const { c } = theme;
  return (
    <View style={{ paddingHorizontal: 20, paddingTop: 18, paddingBottom: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
      <Text style={labelStyle(theme)}>{`${label} · ${scopeLabel}`}</Text>
      <Pressable onPress={onChangeMode} style={{ minHeight: 44, justifyContent: 'center' }}>
        <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: theme.size.caption }}>Change mode</Text>
      </Pressable>
    </View>
  );
}

export default function RetrievalScreen() {
  const theme = useTheme();
  const { c } = theme;
  const params = useLocalSearchParams<{
    concept?: string;
    conceptId?: string;
    conceptState?: string;
    topicId?: string;
    courseId?: string;
    mode?: string;
  }>();

  const topicId = params.topicId;
  const courseId = params.courseId;
  const conceptId = params.conceptId;
  const displayConcept = params.concept ?? 'this concept';
  const rawConceptState = params.conceptState;
  const conceptState: ConceptState | undefined =
    rawConceptState === 'solid' || rawConceptState === 'fading' || rawConceptState === 'shaky' ? rawConceptState : undefined;

  const [mode, setMode] = useState<ModeId>(isModeId(params.mode) ? params.mode : 'quiz');
  const [availableModes, setAvailableModes] = useState<ModeDef[]>(MODES);
  const [profile, setProfile] = useState<TopicProfile | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [stage, setStage] = useState<Stage>('loading');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [challenge, setChallenge] = useState<NextChallenge | null>(null);
  const [freeRecall, setFreeRecall] = useState<FreeRecallChallenge | null>(null);
  const [confidence, setConfidence] = useState<ConfLevel | null>(null);
  const [text, setText] = useState('');
  const [reveal, setReveal] = useState<RevealResult | null>(null);
  const [attempt, setAttempt] = useState<AttemptResult | null>(null);
  const [freeResult, setFreeResult] = useState<FreeRecallResult | null>(null);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [paperHint, setPaperHint] = useState<string | null>(null);
  const [answerOrigin, setAnswerOrigin] = useState<'typed' | 'paper'>('typed');

  const modeDef = MODE_BY_ID.get(mode) ?? MODES[0];

  const resetAnswer = () => {
    setConfidence(null);
    setText('');
    setReveal(null);
    setAttempt(null);
    setFreeResult(null);
    setPaperHint(null);
    setAnswerOrigin('typed');
  };

  // Paper substrate (B8): snap handwriting → transcribe → drop into the editable field, so
  // confirming/correcting the text is the confirm step. answer_origin marks it as paper.
  const snapPaper = async () => {
    setPaperHint(null);
    let files: { uri: string }[];
    try {
      files = await takePhoto();
    } catch (err) {
      setPaperHint(readError(err));
      return;
    }
    if (files.length === 0) return;
    setTranscribing(true);
    try {
      const result = await transcribePaper(files);
      setText(result.transcription);
      setAnswerOrigin('paper');
      setPaperHint(
        result.has_illegible
          ? 'Some words were hard to read — check them before you submit.'
          : result.has_uncertain
            ? 'A few words were uncertain — give it a quick read.'
            : 'Transcribed — check it reads right, then submit.',
      );
    } catch (err) {
      setPaperHint(readError(err));
    } finally {
      setTranscribing(false);
    }
  };

  // GET /modes drives which registry modes are offered; recap/dump are appended when a
  // topic is in scope (they need one). Falls back to the full list if the call fails.
  useEffect(() => {
    let cancelled = false;
    fetchModes()
      .then((infos: ModeInfo[]) => {
        if (cancelled) return;
        const keys = new Set(infos.map((i) => i.key));
        const registry = MODES.filter((m) => m.shape !== 'freerecall' && keys.has(m.id));
        const freeRecallModes = topicId ? MODES.filter((m) => FREE_RECALL_IDS.includes(m.id)) : [];
        const merged = [...registry, ...freeRecallModes];
        if (merged.length > 0) setAvailableModes(merged);
      })
      .catch(() => {
        // Keep the built-in list; a mode picker that can't load its options is worse than a static one.
      });
    return () => {
      cancelled = true;
    };
  }, [topicId]);

  // The topic's subject profile makes the picker context-worthy: mode_mix ranks modes by how
  // well they fit the subject (STEM → quiz/pretest; humanities → ramble/teach). Best-effort.
  useEffect(() => {
    if (!topicId) return;
    let cancelled = false;
    fetchTopicProfile(topicId)
      .then((p) => {
        if (!cancelled) setProfile(p);
      })
      .catch(() => {
        // No profile → the picker just keeps its default order.
      });
    return () => {
      cancelled = true;
    };
  }, [topicId]);

  // Order the offered modes best-fit-first for this subject; the top one is the recommendation.
  const orderedModes = useMemo(() => {
    if (!profile) return availableModes;
    const affinity = (m: ModeDef) => profile.mode_mix[affinityKey(m.id)] ?? 0.5;
    return [...availableModes].sort((a, b) => affinity(b) - affinity(a));
  }, [availableModes, profile]);
  const recommendedId = profile ? orderedModes[0]?.id : undefined;
  const familyLabel = profile ? FAMILY_LABEL[profile.subject_family] : null;

  // Load a challenge for the active mode. useConcept challenges the concept the note
  // handed us; without it the engine selects the next due concept in the topic ("keep going").
  // useConcept challenges the concept the note handed us; false lets the engine pick the
  // next due concept in the topic ("keep going") — labeled by the response's concept_text.
  const loadChallenge = useCallback(
    async (modeId: ModeId, useConcept = true) => {
      const def = MODE_BY_ID.get(modeId) ?? MODES[0];
      resetAnswer();
      setChallenge(null);
      setFreeRecall(null);
      setErrorMsg(null);
      setStage('loading');
      try {
        if (def.shape === 'freerecall') {
          if (!topicId) throw new Error('Open a topic to recap or brain-dump it.');
          const fr = modeId === 'recap' ? await recapNext(topicId) : await dumpNext(topicId);
          setFreeRecall(fr);
        } else {
          if (!topicId && !conceptId) throw new Error('Open a note and tap a concept to start retrieving.');
          const ch = await nextChallenge({
            mode: modeId,
            scope: 'topic',
            topic_id: topicId,
            course_id: courseId,
            concept_id: useConcept ? conceptId : undefined,
          });
          setChallenge(ch);
        }
        setStage('challenge');
      } catch (err) {
        setErrorMsg(readError(err));
        setStage('error');
      }
    },
    [topicId, courseId, conceptId],
  );

  // useFocusEffect (not useEffect) so the synchronous state resets loadChallenge does are
  // outside React's effect-lint scope; it re-runs on mode change (deps) and on refocus.
  useFocusEffect(
    useCallback(() => {
      if (params.mode === 'test') return; // testbuilder passthrough handled below — not a retrieval session
      loadChallenge(mode);
    }, [mode, loadChallenge, params.mode]),
  );

  const changeMode = (m: ModeId) => {
    setPickerOpen(false);
    if (m === mode) {
      loadChallenge(m);
    } else {
      setMode(m);
    }
  };

  const onDone = () => router.back();

  const doAttempt = async (response: unknown) => {
    if (!challenge) return;
    setStage('grading');
    try {
      const res = await submitAttempt({
        challenge_id: challenge.challenge_id,
        response,
        predicted_confidence: confidence?.v ?? null,
        answer_origin: answerOrigin === 'paper' ? 'paper' : undefined,
      });
      setAttempt(res);
      setStage('result');
    } catch (err) {
      setErrorMsg(readError(err));
      setStage('error');
    }
  };

  const doReveal = async () => {
    if (!challenge) return;
    try {
      const r = await revealSolution(challenge.challenge_id, confidence?.v ?? null);
      setReveal(r);
    } catch (err) {
      setErrorMsg(readError(err));
      setStage('error');
    }
  };

  const doFreeRecall = async () => {
    if (!freeRecall) return;
    setStage('grading');
    try {
      const body = {
        challenge_id: freeRecall.challenge_id,
        response: text,
        answer_origin: answerOrigin === 'paper' ? ('paper' as const) : undefined,
      };
      const res = mode === 'recap' ? await recapAttempt(body) : await dumpAttempt(body);
      setFreeResult(res);
      setStage('result');
    } catch (err) {
      setErrorMsg(readError(err));
      setStage('error');
    }
  };

  // End the bout → the warm close (system-spec §5/§6). Summary is best-effort; the close
  // still shows a plain "nice work" if it can't load.
  const finishSession = async () => {
    setStage('loading');
    try {
      setSummary(await fetchSessionSummary(topicId ? { topic_id: topicId } : undefined));
    } catch {
      setSummary(null);
    }
    setStage('close');
  };

  // Continue the session with the next due concept (engine-selected). Nothing left due
  // (404) is the natural end of the bout, not an error — flow into the close.
  const keepGoing = async () => {
    if (!topicId) return;
    resetAnswer();
    setChallenge(null);
    setErrorMsg(null);
    setStage('loading');
    try {
      const ch = await nextChallenge({ mode, scope: 'topic', topic_id: topicId, course_id: courseId });
      setChallenge(ch);
      setStage('challenge');
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 404) {
        await finishSession();
      } else {
        setErrorMsg(readError(err));
        setStage('error');
      }
    }
  };

  // testbuilder (B14 authored practice test) is a distinct concept from scheduled review —
  // its own queue item wires it to /api/practice-tests. Until then its ?mode=test link lands
  // here; we send the user back rather than fake a timed test off the retrieval engine.
  if (params.mode === 'test') {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
        <View style={{ flex: 1, paddingHorizontal: 20, gap: 16, justifyContent: 'center' }}>
          <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display3, color: c.ink }}>Timed tests are coming soon</Text>
          <Text style={{ fontSize: theme.size.body, color: c.inkSecondary }}>
            Authored practice tests aren’t wired up yet. For now, pick a concept in your note to start a review.
          </Text>
          <Button label="Back" onPress={onDone} />
        </View>
      </SafeAreaView>
    );
  }

  // Label from the challenge itself once loaded (so "keep going" shows the right concept),
  // falling back to the name the note handed us before the first challenge arrives.
  const conceptLabel = challenge?.concept_text ?? displayConcept;
  const scopeLabel = modeDef.shape === 'freerecall' ? (mode === 'recap' ? 'Last session' : 'Whole topic') : conceptLabel;

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

  const qtype = challenge?.payload.question_type;
  const isWorked = qtype === 'worked';
  const isMcq = qtype === 'mcq' && Array.isArray(challenge?.payload.answer_options);
  const isNumeric = qtype === 'numeric';
  const promptText = challenge?.prompt ?? freeRecall?.prompt ?? '';

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      {stage !== 'grading' && stage !== 'loading' && stage !== 'close' && (
        <ModeHeader label={modeDef.label} scopeLabel={scopeLabel} onChangeMode={() => setPickerOpen(true)} />
      )}

      <View style={{ flex: 1, paddingHorizontal: 20, gap: 18, justifyContent: 'center' }}>
        {stage === 'loading' && <ActivityIndicator color={c.ink} />}

        {stage === 'grading' && (
          <View style={{ alignItems: 'center', gap: 12 }}>
            <ActivityIndicator color={c.ink} />
            <Text style={{ color: c.inkSecondary, fontSize: theme.size.body }}>Scoring your answer…</Text>
          </View>
        )}

        {stage === 'error' && (
          <View style={{ gap: 14 }}>
            <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display3, color: c.ink }}>Can’t start this yet</Text>
            <Text style={{ fontSize: theme.size.body, color: c.inkSecondary }}>{errorMsg}</Text>
            <Button label="Try again" onPress={() => loadChallenge(mode)} />
            <Button label="Back to reading" variant="text" onPress={onDone} />
          </View>
        )}

        {/* ── Posed (quiz / pretest): challenge → confidence → answer ── */}
        {modeDef.shape === 'posed' && stage === 'challenge' && (
          <>
            {conceptState && <Text style={labelStyle(theme, stateColor[conceptState])}>{conceptState}</Text>}
            <MathText content={promptText} textStyle={questionStyle} />
            {isWorked && (
              <Text style={{ fontSize: theme.size.bodySm, color: c.inkSecondary }}>Work it out on paper — then tell us how sure you are.</Text>
            )}
            <Button label={isWorked ? 'Ready — how sure are you?' : 'How sure are you?'} onPress={() => setStage('confidence')} />
          </>
        )}

        {modeDef.shape === 'posed' && stage === 'confidence' && (
          <>
            <MathText content={promptText} textStyle={questionStyle} />
            <Text style={labelStyle(theme)}>{isWorked ? 'Before you check the solution — how sure are you?' : 'Before you answer — how sure are you?'}</Text>
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
          </>
        )}

        {modeDef.shape === 'posed' && stage === 'answer' && (
          <View style={{ gap: 14 }}>
            <MathText content={promptText} textStyle={questionStyle} />

            {isMcq &&
              (challenge?.payload.answer_options ?? []).map((opt) => (
                <Pressable key={opt} onPress={() => doAttempt(opt)} style={optionButtonStyle}>
                  <Text style={{ fontFamily: theme.font.body, fontSize: 16, color: c.ink }}>{opt}</Text>
                </Pressable>
              ))}

            {isWorked && !reveal && (
              <>
                <Text style={{ fontSize: theme.size.bodySm, color: c.inkSecondary }}>
                  Done on paper? Reveal the full solution, compare it to your work, then mark yourself honestly — comparing your own working to the solution is the learning.
                </Text>
                <Button label="Reveal the worked solution" onPress={doReveal} />
              </>
            )}

            {isWorked && reveal && (
              <>
                <View style={{ padding: 14, borderRadius: theme.radius.md, borderWidth: 1, borderColor: c.paperEdge, backgroundColor: c.paperRecessed }}>
                  <Text style={[labelStyle(theme), { marginBottom: 6 }]}>Worked solution</Text>
                  <MathText content={reveal.worked_solution ?? 'No solution provided.'} textStyle={{ fontSize: theme.size.body, color: c.ink }} />
                </View>
                <Text style={labelStyle(theme)}>How did your work compare?</Text>
                <View style={{ gap: 10 }}>
                  {SELF_GRADES.map((g) => (
                    <Pressable key={g.key} onPress={() => doAttempt(g.key)} style={optionButtonStyle}>
                      <Text style={{ fontFamily: theme.font.body, fontSize: 16, color: c.ink }}>{g.label}</Text>
                    </Pressable>
                  ))}
                </View>
              </>
            )}

            {isNumeric && (
              <>
                <Textarea rows={1} value={text} onChangeText={setText} placeholder="Your answer (a number)…" />
                <Button label="Check" disabled={text.trim().length === 0} onPress={() => doAttempt(text)} />
              </>
            )}

            {!isMcq && !isWorked && !isNumeric && (
              <WrittenAnswer
                value={text}
                onChangeText={setText}
                onSubmit={() => doAttempt(text)}
                onSnapPaper={snapPaper}
                transcribing={transcribing}
                paperHint={paperHint}
              />
            )}
          </View>
        )}

        {/* ── Conversational (teach / ramble): a spoken back-and-forth, one graded attempt ── */}
        {modeDef.shape === 'open' && challenge?.conversational && stage === 'challenge' && (
          <ConversationalBout
            key={challenge.challenge_id}
            challenge={challenge}
            concept={conceptLabel}
            onDone={onDone}
            onKeepGoing={topicId ? keepGoing : undefined}
            onFinish={topicId ? finishSession : undefined}
          />
        )}

        {/* ── Open (ramble / teach) & free-recall (recap / dump): one written response ── */}
        {((modeDef.shape === 'open' && !challenge?.conversational) || modeDef.shape === 'freerecall') && stage === 'challenge' && (
          <>
            <MathText content={promptText} textStyle={questionStyle} />
            {modeDef.shape === 'freerecall' && freeRecall && (
              <Text style={labelStyle(theme)}>{`${freeRecall.concept_count} concept${freeRecall.concept_count === 1 ? '' : 's'} in play — nothing you skip is counted for you`}</Text>
            )}
            <WrittenAnswer
              value={text}
              onChangeText={setText}
              onSubmit={modeDef.shape === 'open' ? () => doAttempt(text) : doFreeRecall}
              onSnapPaper={snapPaper}
              transcribing={transcribing}
              paperHint={paperHint}
              rows={6}
              placeholder="Type everything you can — or snap your handwriting…"
            />
          </>
        )}

        {/* ── Result: posed/open single-concept outcome ── */}
        {stage === 'result' && attempt && (
          <SingleResult
            attempt={attempt}
            objective={isMcq || isNumeric}
            concept={conceptLabel}
            onDone={onDone}
            onKeepGoing={topicId ? keepGoing : undefined}
            onFinish={topicId ? finishSession : undefined}
          />
        )}

        {/* ── Result: free-recall per-concept outcomes ── */}
        {stage === 'result' && freeResult && <FreeRecallResultView result={freeResult} onDone={onDone} />}

        {/* ── The warm close (system-spec §6) ── */}
        {stage === 'close' && <CloseView summary={summary} onDone={onDone} />}
      </View>

      {(stage === 'challenge' || stage === 'confidence' || stage === 'answer') && (
        <Pressable onPress={onDone} style={{ marginHorizontal: 20, marginBottom: 20, minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ color: c.inkSecondary, fontSize: 14 }}>← Back to reading</Text>
        </Pressable>
      )}

      <ModePicker
        open={pickerOpen}
        modes={orderedModes}
        recommendedId={recommendedId}
        familyLabel={familyLabel}
        onPick={changeMode}
        onClose={() => setPickerOpen(false)}
      />
    </SafeAreaView>
  );
}

interface FreeRecallResultViewProps {
  result: FreeRecallResult;
  onDone: () => void;
}

function FreeRecallResultView({ result, onDone }: FreeRecallResultViewProps) {
  const theme = useTheme();
  const { c } = theme;
  return (
    <View style={{ gap: 14 }}>
      <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display3, color: c.ink }}>Graded across the whole set</Text>
      <Text style={{ fontSize: theme.size.bodySm, color: c.inkSecondary }}>{`${result.concept_count} concept${result.concept_count === 1 ? '' : 's'} · ${Math.round(result.mean_score * 100)}% on average`}</Text>
      <View style={{ gap: 10 }}>
        {result.outcomes.map((o) => (
          <View key={o.concept_id} style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: c.paperEdge }}>
            <Text style={{ color: c.ink, fontSize: theme.size.body, flex: 1, paddingRight: 12 }}>{o.concept_text}</Text>
            <Text style={labelStyle(theme, gradeColor(theme, o.grade))}>{o.grade}</Text>
          </View>
        ))}
      </View>
      <Button label="Back to reading" onPress={onDone} />
    </View>
  );
}

const CLOSE_CALIBRATION: Record<CalibrationLabel, string> = {
  calibrated: 'Your confidence tracked reality well today.',
  underconfident: 'You knew more than you let on — trust yourself a little more.',
  overconfident: 'You ran a bit hot on confidence — worth noticing.',
};

interface CloseViewProps {
  summary: SessionSummary | null;
  onDone: () => void;
}

// The warm close (system-spec §6): lead with growth, whisper the fading, offer the hook.
function CloseView({ summary, onDone }: CloseViewProps) {
  const theme = useTheme();
  const { c } = theme;
  const firmed = summary?.firmed.length ?? 0;
  const slipping = summary?.slipping ?? [];

  const headline = firmed > 0 ? `You firmed up ${firmed} concept${firmed === 1 ? '' : 's'}` : 'That was a good push';

  return (
    <View style={{ gap: 14 }}>
      <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display2, lineHeight: theme.size.display2 * theme.lineHeight.display, color: c.ink }}>
        {headline}
      </Text>

      {slipping.length > 0 && (
        <Text style={{ fontSize: theme.size.body, color: c.inkSecondary }}>
          {`${slipping.length} still shaky — ${slipping.map((s) => s.concept_text).slice(0, 3).join(', ')}. Recalling them again tomorrow is what makes them stick.`}
        </Text>
      )}

      {summary && summary.predicted_count > 0 && summary.calibration_label && (
        <Text style={labelStyle(theme)}>{CLOSE_CALIBRATION[summary.calibration_label]}</Text>
      )}

      <Text style={{ fontSize: theme.size.bodySm, color: c.inkTertiary }}>
        Come back tomorrow and recap — spacing is the part that lasts.
      </Text>

      <Button label="Back to reading" onPress={onDone} />
    </View>
  );
}
