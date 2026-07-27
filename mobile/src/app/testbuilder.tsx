import React, { useEffect, useState } from 'react';
import { ScrollView, StyleProp, Text, TextStyle, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Chip } from '@/components/ui/Chip';
import { IconButton } from '@/components/ui/IconButton';
import { Radio } from '@/components/ui/Radio';

type Stage = 'build' | 'generating' | 'ready';

const TOPICS = ['Glycolysis', 'Krebs cycle', 'Electron transport chain', 'Photosynthesis'];
const COUNTS = [5, 10, 20];
const TYPES = ['Multiple choice', 'Short answer', 'Mixed'];
const GENERATE_TICK_MS = 120;

function Label({ children }: { children: string }) {
  const { c, font, size, trackingUtility } = useTheme();
  return (
    <Text
      style={{
        fontFamily: font.utility,
        fontSize: size.utility,
        letterSpacing: trackingUtility(size.utility),
        textTransform: 'uppercase',
        color: c.inkSecondary,
      }}
    >
      {children}
    </Text>
  );
}

export default function TestBuilder() {
  const { c, font, size, space, radius } = useTheme();
  const [stage, setStage] = useState<Stage>('build');
  const [selected, setSelected] = useState<string[]>(['Glycolysis', 'Krebs cycle']);
  const [count, setCount] = useState(10);
  const [type, setType] = useState('Mixed');
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (stage !== 'generating') return;
    setProgress(0);
    const id = setInterval(() => {
      setProgress((p) => {
        if (p >= count) {
          clearInterval(id);
          setStage('ready');
          return p;
        }
        return p + 1;
      });
    }, GENERATE_TICK_MS);
    return () => clearInterval(id);
  }, [stage]);

  const toggle = (topic: string) =>
    setSelected((s) => (s.includes(topic) ? s.filter((x) => x !== topic) : [...s, topic]));

  const titleStyle: StyleProp<TextStyle> = { fontFamily: font.display, fontSize: size.display3, color: c.ink };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text style={titleStyle}>Build a practice test</Text>
        <IconButton icon={<Text style={{ fontSize: 20, color: c.inkSecondary }}>✕</Text>} label="Close" onPress={() => router.back()} />
      </View>

      <ScrollView contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 20 }}>
        {stage === 'build' && (
          <View style={{ gap: 22 }}>
            <View>
              <Label>Topics</Label>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
                {TOPICS.map((t) => (
                  <Chip key={t} label={t} selected={selected.includes(t)} onPress={() => toggle(t)} />
                ))}
              </View>
            </View>

            <View>
              <Label>Number of questions</Label>
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
                {COUNTS.map((cnt) => (
                  <Chip key={cnt} label={String(cnt)} selected={count === cnt} onPress={() => setCount(cnt)} />
                ))}
              </View>
            </View>

            <View>
              <Label>Question type</Label>
              <View style={{ marginTop: 4 }}>
                {TYPES.map((t) => (
                  <View key={t} style={{ borderBottomWidth: 1, borderBottomColor: c.paperEdge }}>
                    <Radio label={t} checked={type === t} onPress={() => setType(t)} />
                  </View>
                ))}
              </View>
            </View>

            <Button label="Generate" disabled={selected.length === 0} onPress={() => setStage('generating')} />

            <View style={{ borderTopWidth: 1, borderTopColor: c.paperEdge, marginTop: 8, paddingTop: 16 }}>
              <Label>Shared in this course</Label>
              <Text style={{ marginTop: 8, fontSize: size.bodySm, color: c.inkSecondary }}>
                Ada made a 20-q mock on Unit 3 — no scores shown, just who’s taken it.
              </Text>
            </View>
          </View>
        )}

        {stage === 'generating' && (
          <View style={{ paddingTop: 60, alignItems: 'center', gap: 16 }}>
            <Text style={titleStyle}>Writing your questions</Text>
            <Label>{`${progress} of ${count}`}</Label>
            <View style={{ width: '100%', height: 4, backgroundColor: c.paperEdge, borderRadius: radius.pill, overflow: 'hidden' }}>
              <View style={{ width: `${(progress / count) * 100}%`, height: '100%', backgroundColor: c.ink }} />
            </View>
          </View>
        )}

        {stage === 'ready' && (
          <View style={{ paddingTop: 40, gap: 14 }}>
            <Text style={titleStyle}>{`${count}-question test ready`}</Text>
            <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>{`${selected.join(', ')} · ${type}`}</Text>
            <Button
              label="Take it now"
              onPress={() =>
                router.push({
                  pathname: '/retrieval',
                  params: { mode: 'test', count: String(count), type, topics: selected.join(',') },
                })
              }
            />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
