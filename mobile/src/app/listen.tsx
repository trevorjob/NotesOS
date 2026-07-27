import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';

const TAKES = ['Take 1 · overview', 'Take 2 · exam-focused', 'Take 3 · slower pace'];

export default function ListenScreen() {
  const { c, font, size, space, radius, trackingUtility } = useTheme();
  const [playing, setPlaying] = useState(false);
  const [take, setTake] = useState(0);
  const [activeListen, setActiveListen] = useState(false);
  const [progress] = useState(35);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10 }}>
        <Pressable onPress={() => router.back()} style={{ minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>← Note</Text>
        </Pressable>
        <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink, marginTop: 4 }}>Listen — Cellular Respiration</Text>
      </View>

      <View style={{ flex: 1, paddingHorizontal: space.gutterPage, justifyContent: 'center', gap: 24 }}>
        <Text
          style={{
            fontFamily: font.utility,
            fontSize: size.caption,
            letterSpacing: trackingUtility(size.caption),
            textTransform: 'uppercase',
            color: c.inkTertiary,
          }}
        >
          {TAKES[take]}
        </Text>

        <View style={{ width: '100%', height: 4, backgroundColor: c.paperEdge, borderRadius: radius.pill, overflow: 'hidden' }}>
          <View style={{ width: `${progress}%`, height: '100%', backgroundColor: c.ink }} />
        </View>

        <Button label={playing ? 'Pause' : 'Play'} onPress={() => setPlaying(!playing)} style={{ width: '100%' }} />

        <View style={{ gap: 8 }}>
          {TAKES.map((t, i) => (
            <Pressable
              key={t}
              onPress={() => setTake(i)}
              style={{
                paddingVertical: 10,
                borderBottomWidth: 1,
                borderBottomColor: c.paperEdge,
                minHeight: 44,
                justifyContent: 'center',
              }}
            >
              <Text style={{ fontWeight: take === i ? '600' : '400', color: take === i ? c.ink : c.inkSecondary }}>{t}</Text>
            </Pressable>
          ))}
        </View>

        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', minHeight: 44 }}>
          <Text style={{ color: c.ink, flex: 1 }}>Active-listen (pause to answer out loud)</Text>
          <Switch checked={activeListen} onChange={setActiveListen} />
        </View>

        <Pressable style={{ minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>Download for offline</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}
