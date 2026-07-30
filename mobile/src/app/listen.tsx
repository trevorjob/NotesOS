import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { setAudioModeAsync, useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { WeakConceptSuggestion } from '@/components/note/WeakConceptSuggestion';
import { WaveformVisualizer } from '@/components/audio/WaveformVisualizer';
import {
  AudioArtifact,
  AudioLens,
  AudioScopeType,
  fetchAudioArtifact,
  regenerateAudio,
  requestAudio,
} from '@/lib/audio';

// Three entry shapes into one screen (docs/listen-audio-plan.md):
//   - Topic mode (default): browse lens presets over the topic's shared/personal audio,
//     plus a remediation suggestion (Phase 2 §6) for the topic's shakiest concept.
//   - Concept mode, user_instruction (from "Explain this my way" on a concept):
//     conceptId+instruction, no picker.
//   - Concept mode, remediation (from a weak-concept suggestion): conceptId+lens=remediation,
//     no instruction — the worker grounds itself in the caller's actual wrong answers.

const POLL_INTERVAL_MS = 4000;

const LENS_OPTIONS: { lens: AudioLens; label: string }[] = [
  { lens: 'default', label: 'Overview' },
  { lens: 'exam_focused', label: 'Exam-focused' },
  { lens: 'slower', label: 'Slower' },
  { lens: 'worked_example', label: 'Worked example' },
];

// Lenses that are just angles on the same narrated note as the default explainer —
// withheld for calc-heavy topics (docs/listen-audio-plan.md §7). worked_example
// (narrates solved-problem steps) is the one that still works for those.
const GENERIC_EXPLAINER_LENSES = new Set<AudioLens>(['default', 'exam_focused', 'slower']);

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds || 0));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function ListenScreen() {
  const { c, font, size, space, radius, trackingUtility } = useTheme();
  const { topicId, courseId, conceptId, conceptTerm, instruction, lens: lensParam } = useLocalSearchParams<{
    topicId?: string;
    courseId?: string;
    conceptId?: string;
    conceptTerm?: string;
    instruction?: string;
    lens?: AudioLens;
  }>();

  const isConceptMode = !!conceptId;
  const scopeType: AudioScopeType = isConceptMode ? 'concept' : 'topic';
  const scopeRef = isConceptMode ? conceptId : topicId;
  const isRemediation = lensParam === 'remediation';

  const [lens, setLens] = useState<AudioLens>(lensParam ?? (isConceptMode ? 'user_instruction' : 'default'));
  const [artifact, setArtifact] = useState<AudioArtifact | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const barWidthRef = useRef(1);

  const load = useCallback(async () => {
    if (!scopeRef) {
      setError('Nothing selected.');
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const a = await fetchAudioArtifact(scopeType, scopeRef, {
        lens,
        owner: lens === 'default' ? 'global' : 'me',
      });
      // Calc-heavy topics withhold the generic explainer lenses (§7) — steer off
      // one as soon as we learn the scope doesn't suit it, before Generate 422s.
      if (!a.audio_suitable && GENERIC_EXPLAINER_LENSES.has(lens) && lens !== 'worked_example') {
        setLens('worked_example');
        return;
      }
      setArtifact(a);
      setError(null);
    } catch {
      setError('Could not load this lesson. Pull to retry.');
    } finally {
      setLoading(false);
    }
  }, [scopeType, scopeRef, lens]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  // Poll while a generation is in flight — cheap and short-lived, one screen at a time.
  useEffect(() => {
    const inFlight = artifact?.status === 'pending' || artifact?.status === 'processing';
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (inFlight && scopeRef) {
      pollRef.current = setInterval(load, POLL_INTERVAL_MS);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [artifact?.status, scopeRef, load]);

  useEffect(() => {
    setAudioModeAsync({ playsInSilentMode: true }).catch(() => {});
  }, []);

  const player = useAudioPlayer(artifact?.audio_url ?? null);
  const playerStatus = useAudioPlayerStatus(player);

  const handleGenerate = async () => {
    if (!scopeRef || requesting) return;
    setRequesting(true);
    try {
      if (lens === 'default') {
        await regenerateAudio(scopeType, scopeRef);
      } else {
        await requestAudio(scopeType, scopeRef, lens, lens === 'user_instruction' ? instruction : undefined);
      }
      await load();
    } catch {
      setError('Could not start generating this lesson. Try again.');
    } finally {
      setRequesting(false);
    }
  };

  const togglePlay = () => {
    if (playerStatus.playing) player.pause();
    else player.play();
  };

  const seekTo = (ratio: number) => {
    if (!playerStatus.duration) return;
    player.seekTo(ratio * playerStatus.duration);
  };

  const isReady = artifact?.status === 'completed' && !!artifact.audio_url;
  const title = isConceptMode ? `Listen — ${conceptTerm ?? 'concept'}` : 'Listen';
  const suitable = artifact?.audio_suitable ?? true;
  const visibleLensOptions = suitable ? LENS_OPTIONS : LENS_OPTIONS.filter((o) => o.lens === 'worked_example');

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10 }}>
        <Pressable onPress={() => router.back()} style={{ minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>← Note</Text>
        </Pressable>
        <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink, marginTop: 4 }}>
          {title}
        </Text>
      </View>

      {!isConceptMode && (
        <View style={{ paddingHorizontal: space.gutterPage, gap: 6 }}>
          {!suitable && (
            <Text style={{ fontSize: size.bodySm, color: c.inkSecondary }}>
              This topic is calculation-heavy — audio works best as a worked example.
            </Text>
          )}
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {visibleLensOptions.map((opt) => (
              <Pressable
                key={opt.lens}
                onPress={() => setLens(opt.lens)}
                style={{
                  paddingHorizontal: 14,
                  paddingVertical: 8,
                  minHeight: 36,
                  justifyContent: 'center',
                  borderRadius: radius.pill,
                  borderWidth: 1,
                  borderColor: lens === opt.lens ? c.ink : c.paperEdge,
                  backgroundColor: lens === opt.lens ? c.ink : 'transparent',
                }}
              >
                <Text style={{ fontSize: size.bodySm, color: lens === opt.lens ? c.paper : c.inkSecondary }}>
                  {opt.label}
                </Text>
              </Pressable>
            ))}
          </View>
          {lens !== 'default' && (
            <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>Generated just for you.</Text>
          )}
        </View>
      )}

      {!isConceptMode && <WeakConceptSuggestion topicId={topicId} courseId={courseId} />}

      <View style={{ flex: 1, paddingHorizontal: space.gutterPage, justifyContent: 'center', gap: 24 }}>
        {loading ? (
          <ActivityIndicator color={c.ink} />
        ) : error ? (
          <View style={{ alignItems: 'center', gap: 12 }}>
            <Text style={{ color: c.inkSecondary, fontSize: size.body, textAlign: 'center' }}>{error}</Text>
            <Button label="Try again" variant="secondary" onPress={load} />
          </View>
        ) : !artifact || artifact.status === 'pending' ? (
          <View style={{ alignItems: 'center', gap: 12 }}>
            <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink }}>No lesson yet</Text>
            <Text style={{ color: c.inkSecondary, fontSize: size.bodySm, maxWidth: 260, textAlign: 'center' }}>
              {isRemediation
                ? `Get a targeted breakdown of "${conceptTerm}" — grounded in what you've actually gotten wrong.`
                : isConceptMode
                ? `Generate a spoken explainer for "${instruction}".`
                : "Generate a spoken explainer of this topic's note."}
            </Text>
            <Button label="Generate audio" onPress={handleGenerate} disabled={requesting} />
          </View>
        ) : artifact.status === 'processing' ? (
          <View style={{ alignItems: 'center', gap: 12 }}>
            <ActivityIndicator color={c.ink} />
            <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>Generating the lesson…</Text>
          </View>
        ) : artifact.status === 'failed' ? (
          <View style={{ alignItems: 'center', gap: 12 }}>
            <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink }}>Generation hit a snag</Text>
            <Text style={{ color: c.inkSecondary, fontSize: size.bodySm, maxWidth: 280, textAlign: 'center' }}>
              {artifact.error_message || 'The lesson could not be generated.'}
            </Text>
            <Button label="Try again" variant="secondary" onPress={handleGenerate} disabled={requesting} />
          </View>
        ) : isReady ? (
          <>
            <Text
              style={{
                fontFamily: font.utility,
                fontSize: size.caption,
                letterSpacing: trackingUtility(size.caption),
                textTransform: 'uppercase',
                color: c.inkTertiary,
              }}
            >
              {LENS_OPTIONS.find((o) => o.lens === lens)?.label ?? 'Your lesson'}
            </Text>

            <WaveformVisualizer playing={playerStatus.playing} />

            <Pressable
              onLayout={(e) => {
                barWidthRef.current = e.nativeEvent.layout.width || 1;
              }}
              onPress={(e) => seekTo(Math.min(1, Math.max(0, e.nativeEvent.locationX / barWidthRef.current)))}
              hitSlop={{ top: 16, bottom: 16 }}
              style={{ width: '100%', height: 4, backgroundColor: c.paperEdge, borderRadius: radius.pill, overflow: 'hidden' }}
            >
              <View
                style={{
                  width: `${playerStatus.duration ? (playerStatus.currentTime / playerStatus.duration) * 100 : 0}%`,
                  height: '100%',
                  backgroundColor: c.ink,
                }}
              />
            </Pressable>

            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <Text style={{ fontSize: size.bodySm, color: c.inkTertiary }}>{formatTime(playerStatus.currentTime)}</Text>
              <Text style={{ fontSize: size.bodySm, color: c.inkTertiary }}>{formatTime(playerStatus.duration)}</Text>
            </View>

            <Button label={playerStatus.playing ? 'Pause' : 'Play'} onPress={togglePlay} style={{ width: '100%' }} />
          </>
        ) : null}
      </View>
    </SafeAreaView>
  );
}
