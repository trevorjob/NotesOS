import React, { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';

interface SourceResource {
  name: string;
  quarantined: boolean;
}

const RESOURCES: SourceResource[] = [
  { name: 'Lecture 4 — Respiration.pdf', quarantined: false },
  { name: 'Recording_Sept14.m4a (transcribed)', quarantined: false },
  { name: 'IMG_0491.jpg (transcribed)', quarantined: true },
];

export default function SourceScreen() {
  const { c, font, size, space, trackingUtility, lineHeight } = useTheme();
  const [open, setOpen] = useState(0);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10 }}>
        <Pressable onPress={() => router.back()} style={{ minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>← Note</Text>
        </Pressable>
        <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink, marginTop: 4 }}>Read the original</Text>
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 20 }}>
        {RESOURCES.map((r, i) => (
          <View key={r.name}>
            <Pressable
              onPress={() => setOpen(open === i ? -1 : i)}
              style={{
                paddingVertical: 12,
                borderBottomWidth: 1,
                borderBottomColor: c.paperEdge,
                minHeight: 44,
                flexDirection: 'row',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <Text style={{ fontWeight: '600', color: c.ink }}>{r.name}</Text>
              {r.quarantined && (
                <Text
                  style={{
                    fontFamily: font.utility,
                    fontSize: size.caption,
                    letterSpacing: trackingUtility(size.caption),
                    textTransform: 'uppercase',
                    color: c.inkTertiary,
                  }}
                >
                  Held · only you
                </Text>
              )}
            </Pressable>
            {open === i && (
              <Text style={{ paddingVertical: 12, color: c.inkSecondary, fontSize: size.bodySm, lineHeight: size.bodySm * lineHeight.body }}>
                Verbatim transcription would render here — the exact uploaded or transcribed text, unshaped and unsynthesized.
              </Text>
            )}
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
