import React, { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';

type Stage = 'permission' | 'idle' | 'listening' | 'thinking' | 'speaking' | 'interrupted' | 'done' | 'blocked';
type BlockedReason = 'denied' | 'offline' | null;

const ORB_LABEL: Record<'idle' | 'listening' | 'thinking' | 'speaking' | 'interrupted', string> = {
  idle: 'Tap to speak',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
  interrupted: 'Go ahead',
};

export default function VoiceScreen() {
  const theme = useTheme();
  const { c } = theme;
  const params = useLocalSearchParams<{ concept?: string }>();
  const displayConcept = params.concept || 'Cellular Respiration';

  const [stage, setStage] = useState<Stage>('permission');
  const [blockedReason, setBlockedReason] = useState<BlockedReason>(null);
  const [turns, setTurns] = useState(0);

  useEffect(() => {
    if (stage === 'listening') {
      const t = setTimeout(() => setStage('thinking'), 1600);
      return () => clearTimeout(t);
    }
    if (stage === 'thinking') {
      const t = setTimeout(() => {
        setTurns((n) => n + 1);
        setStage('speaking');
      }, 1200);
      return () => clearTimeout(t);
    }
  }, [stage]);

  const onDone = () => router.back();
  const onBack = () => router.back();

  if (stage === 'blocked') {
    const copy =
      blockedReason === 'denied'
        ? { t: 'Microphone blocked', d: 'Voice needs mic access to hear you. Enable it in your device settings, or try a typed quiz instead.' }
        : { t: 'Voice needs a connection', d: 'Everything else here still works offline — try a typed quiz instead.' };
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', gap: 14, padding: 20 }}>
          <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display3, color: c.ink, textAlign: 'center' }}>{copy.t}</Text>
          <Text style={{ color: c.inkSecondary, fontSize: theme.size.bodySm, maxWidth: 280, textAlign: 'center' }}>{copy.d}</Text>
          <Pressable
            onPress={onBack}
            style={{ minHeight: 44, borderWidth: 1, borderColor: c.paperEdge, borderRadius: theme.radius.md, paddingHorizontal: 18, paddingVertical: 10, justifyContent: 'center', alignItems: 'center' }}
          >
            <Text style={{ fontSize: 16, color: c.ink }}>Back</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  if (stage === 'done') {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', gap: 14, padding: 20 }}>
          <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display3, color: c.ink, textAlign: 'center' }}>Nice talk.</Text>
          <Text style={{ color: c.inkSecondary, fontSize: theme.size.bodySm, maxWidth: 280, textAlign: 'center' }}>
            {`You talked through ${displayConcept} — ${turns} exchange${turns === 1 ? '' : 's'}.`}
          </Text>
          <Button label="Return" onPress={onDone} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ paddingHorizontal: 20, paddingTop: 18, paddingBottom: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text
          style={{
            fontFamily: theme.font.utility,
            fontSize: theme.size.caption,
            letterSpacing: theme.trackingUtility(theme.size.caption),
            textTransform: 'uppercase',
            color: c.inkTertiary,
          }}
        >
          Voice · preview, ships dark at launch
        </Text>
        <Pressable
          onPress={() => {
            setBlockedReason('offline');
            setStage('blocked');
          }}
          style={{ minHeight: 44, justifyContent: 'center' }}
        >
          <Text style={{ fontSize: theme.size.caption, color: c.inkTertiary }}>Simulate offline</Text>
        </Pressable>
      </View>

      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', gap: 20, padding: 20 }}>
        {stage === 'permission' && (
          <>
            <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display3, color: c.ink, textAlign: 'center' }}>Talk it through</Text>
            <Text style={{ fontSize: theme.size.bodySm, color: c.inkTertiary, textAlign: 'center' }}>{displayConcept}</Text>
            <Text style={{ color: c.inkSecondary, fontSize: theme.size.bodySm, textAlign: 'center', maxWidth: 280 }}>
              NotesOS needs your microphone to hear your answer. Nothing is recorded without this.
            </Text>
            <Button label="Allow microphone" onPress={() => setStage('idle')} />
            <Pressable
              onPress={() => {
                setBlockedReason('denied');
                setStage('blocked');
              }}
              style={{ minHeight: 44, justifyContent: 'center', alignItems: 'center' }}
            >
              <Text style={{ fontSize: theme.size.bodySm, color: c.inkTertiary, textDecorationLine: 'underline' }}>Not now</Text>
            </Pressable>
          </>
        )}

        {stage !== 'permission' && (
          <View
            style={{
              width: 120,
              height: 120,
              borderRadius: 60,
              borderWidth: 3,
              borderColor: stage === 'listening' ? c.confirm : stage === 'speaking' ? c.stateSolid : c.paperEdge,
              justifyContent: 'center',
              alignItems: 'center',
            }}
          >
            <Text
              style={{
                fontFamily: theme.font.utility,
                fontSize: theme.size.caption,
                letterSpacing: theme.trackingUtility(theme.size.caption),
                textTransform: 'uppercase',
                color: c.inkSecondary,
              }}
            >
              {ORB_LABEL[stage]}
            </Text>
          </View>
        )}

        {stage === 'idle' && <Button label="Start" onPress={() => setStage('listening')} />}

        {stage === 'speaking' && (
          <Pressable
            onPress={() => setStage('interrupted')}
            style={{ minHeight: 44, borderWidth: 1, borderColor: c.paperEdge, borderRadius: theme.radius.md, paddingHorizontal: 18, paddingVertical: 10, justifyContent: 'center', alignItems: 'center' }}
          >
            <Text style={{ fontSize: 16, color: c.ink }}>Jump in</Text>
          </Pressable>
        )}

        {(stage === 'speaking' || stage === 'interrupted') && (
          <Pressable onPress={() => setStage('done')} style={{ minHeight: 44, justifyContent: 'center', alignItems: 'center' }}>
            <Text style={{ fontSize: 14, color: c.inkSecondary }}>End session</Text>
          </Pressable>
        )}
      </View>
    </SafeAreaView>
  );
}
