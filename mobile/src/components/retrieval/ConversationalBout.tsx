import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { MathText } from '@/components/retrieval/MathText';
import { usePushToTalk } from '@/components/retrieval/usePushToTalk';
import { useSpeechOut } from '@/components/retrieval/useSpeechOut';
import {
  CONF_LEVELS,
  ConfLevel,
  SingleResult,
  labelStyle,
} from '@/components/retrieval/retrievalShared';
import {
  AttemptResult,
  ConversationTurnResult,
  NextChallenge,
  submitTurn,
} from '@/lib/retrieval';

type Role = 'ai' | 'user';
interface Line {
  role: Role;
  text: string;
}
type Phase = 'confidence' | 'talking' | 'result' | 'error';

interface Props {
  challenge: NextChallenge;
  concept: string;
  onDone: () => void;
  onKeepGoing?: () => void;
  onFinish?: () => void;
}

// A conversational retrieval bout (teach / ramble): predicted confidence at open, then a
// spoken back-and-forth the AI digs into, closing to one graded attempt (conversational-modes
// §9). Push-to-talk auto-advances with no confirm. The turn cap is enforced server-side and
// kept invisible — it's a graceful ceiling, not a countdown for the user to watch. Keyed by
// challenge_id upstream so each new bout mounts fresh.
export function ConversationalBout({ challenge, concept, onDone, onKeepGoing, onFinish }: Props) {
  const theme = useTheme();
  const { c } = theme;

  const [phase, setPhase] = useState<Phase>('confidence');
  const [lines, setLines] = useState<Line[]>([{ role: 'ai', text: challenge.prompt }]);
  const [confidence, setConfidence] = useState<ConfLevel | null>(null);
  const [thinking, setThinking] = useState(false);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const busyRef = useRef(false);
  const sentFirstRef = useRef(false);
  const scrollRef = useRef<ScrollView>(null);
  const speech = useSpeechOut();

  useEffect(() => {
    scrollRef.current?.scrollToEnd({ animated: true });
  }, [lines, thinking]);

  const finishBout = useCallback(
    (res: ConversationTurnResult) => {
      speech.stop();
      if (res.outcome && res.state && res.calibration && res.concept_id && res.mode) {
        setResult({
          concept_id: res.concept_id,
          mode: res.mode,
          outcome: res.outcome,
          state: res.state,
          calibration: res.calibration,
        });
      }
      setPhase('result');
    },
    [speech],
  );

  const sendTurn = useCallback(
    async (message: string, end = false) => {
      if (busyRef.current) return;
      busyRef.current = true;
      setThinking(true);
      const predicted = sentFirstRef.current ? undefined : confidence?.v ?? null;
      sentFirstRef.current = true;
      if (message) setLines((prev) => [...prev, { role: 'user', text: message }]);
      try {
        const res = await submitTurn({
          challenge_id: challenge.challenge_id,
          message,
          predicted_confidence: predicted,
          end,
        });
        if (res.closed) {
          finishBout(res);
        } else if (res.reply) {
          setLines((prev) => [...prev, { role: 'ai', text: res.reply as string }]);
          speech.speak(res.reply);
        }
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : 'That didn’t go through — try again.');
        setPhase('error');
      } finally {
        setThinking(false);
        busyRef.current = false;
      }
    },
    [challenge.challenge_id, confidence, finishBout, speech],
  );

  const ptt = usePushToTalk(sendTurn);

  const pickConfidence = (lvl: ConfLevel) => {
    setConfidence(lvl);
    setPhase('talking');
    speech.speak(challenge.prompt);
  };

  if (phase === 'error') {
    return (
      <View style={{ gap: 14 }}>
        <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display3, color: c.ink }}>Lost the thread</Text>
        <Text style={{ fontSize: theme.size.body, color: c.inkSecondary }}>{errorMsg}</Text>
        <Button label="Back to reading" onPress={onDone} />
      </View>
    );
  }

  if (phase === 'result') {
    if (result) {
      return <SingleResult attempt={result} objective={false} concept={concept} onDone={onDone} onKeepGoing={onKeepGoing} onFinish={onFinish} />;
    }
    return (
      <View style={{ gap: 14 }}>
        <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display3, color: c.ink }}>Nice — that’s logged.</Text>
        {onKeepGoing && <Button label="Keep going" onPress={onKeepGoing} />}
        <Button label="Back to reading" variant={onKeepGoing ? 'text' : undefined} onPress={onDone} />
      </View>
    );
  }

  if (phase === 'confidence') {
    return (
      <View style={{ gap: 16 }}>
        <MathText content={challenge.prompt} textStyle={{ fontFamily: theme.font.display, fontWeight: '500', fontSize: theme.size.display3, lineHeight: theme.size.display3 * theme.lineHeight.display, color: c.ink }} />
        <Text style={labelStyle(theme)}>Before you start — how well do you know this?</Text>
        <View style={{ gap: 10 }}>
          {CONF_LEVELS.map((lvl) => (
            <Pressable
              key={lvl.label}
              onPress={() => pickConfidence(lvl)}
              style={{ minHeight: 44, paddingHorizontal: 14, paddingVertical: 12, borderRadius: theme.radius.md, borderWidth: 1, borderColor: c.paperEdge, backgroundColor: c.paper, justifyContent: 'center' }}
            >
              <Text style={{ fontFamily: theme.font.body, fontSize: 16, color: c.ink }}>{lvl.label}</Text>
            </Pressable>
          ))}
        </View>
      </View>
    );
  }

  // phase === 'talking'
  return (
    <View style={{ flex: 1, gap: 12 }}>
      <Pressable onPress={speech.toggleMuted} style={{ alignSelf: 'flex-end', minHeight: 36, minWidth: 44, alignItems: 'flex-end', justifyContent: 'center' }} accessibilityLabel={speech.muted ? 'Unmute the voice' : 'Mute the voice'}>
        <Text style={{ fontSize: 18 }}>{speech.muted ? '🔇' : '🔊'}</Text>
      </Pressable>

      <ScrollView ref={scrollRef} style={{ flex: 1 }} contentContainerStyle={{ gap: 10, paddingBottom: 8 }} keyboardShouldPersistTaps="handled">
        {lines.map((line, i) => (
          <Bubble key={i} role={line.role} text={line.text} />
        ))}
        {ptt.recording && ptt.partial.length > 0 && <Bubble role="user" text={ptt.partial} pending />}
        {thinking && (
          <View style={{ alignSelf: 'flex-start', paddingHorizontal: 14, paddingVertical: 10, borderRadius: theme.radius.md, backgroundColor: c.paperRecessed }}>
            <ActivityIndicator color={c.inkSecondary} />
          </View>
        )}
      </ScrollView>

      {ptt.error && <Text style={{ fontSize: theme.size.bodySm, color: c.stateShaky }}>{ptt.error}</Text>}

      <Pressable
        onPress={() => (ptt.recording ? ptt.stop() : ptt.start())}
        disabled={thinking}
        style={{
          minHeight: 56,
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          borderRadius: theme.radius.md,
          borderWidth: 1.5,
          borderColor: ptt.recording ? c.confirm : c.paperEdge,
          backgroundColor: ptt.recording ? c.highlighterTint : c.paperRecessed,
          opacity: thinking ? 0.5 : 1,
        }}
      >
        <Text style={{ color: ptt.recording ? c.confirm : c.ink, fontSize: 16, fontFamily: theme.font.bodySemibold }}>
          {ptt.recording ? '● Listening — tap to send' : '🎤 Tap to speak'}
        </Text>
      </Pressable>

      <Pressable onPress={() => sendTurn('', true)} disabled={thinking || ptt.recording} style={{ minHeight: 44, justifyContent: 'center', alignItems: 'center' }}>
        <Text style={{ color: c.inkSecondary, fontSize: 14, opacity: thinking || ptt.recording ? 0.4 : 1 }}>Done — grade what I’ve got</Text>
      </Pressable>
    </View>
  );
}

interface BubbleProps {
  role: Role;
  text: string;
  pending?: boolean;
}

function Bubble({ role, text, pending }: BubbleProps) {
  const theme = useTheme();
  const { c } = theme;
  const mine = role === 'user';
  return (
    <View
      style={{
        alignSelf: mine ? 'flex-end' : 'flex-start',
        maxWidth: '86%',
        paddingHorizontal: 14,
        paddingVertical: 10,
        borderRadius: theme.radius.md,
        backgroundColor: mine ? c.highlighterTint : c.paperRecessed,
        opacity: pending ? 0.6 : 1,
      }}
    >
      <MathText content={text} textStyle={{ fontSize: theme.size.body, color: c.ink }} />
    </View>
  );
}
