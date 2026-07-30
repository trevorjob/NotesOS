import React, { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { NextAction, fetchNextAction } from '@/lib/retrieval';

// The note-scoped study doorway (retrieval-experience.md): when you've read the note, the
// engine offers the single best thing to do NEXT on THIS topic (accept with one tap), plus a
// row of note-scoped modes to override with, and a path to the test builder. Everything here
// stays pinned to this topic_id — never a global concept, which is the whole point.

const ACTION_LEAD: Record<NextAction['kind'], string> = {
  review: 'Fading — worth firming up',
  calibration: 'Sure but missed — recheck',
  dump: 'Fresh read — dump it while it’s warm',
  new: 'New — a quick pretest primes it',
  get_ahead: 'Read it — now make it stick',
};

// Note-scoped overrides. Engine picks the concept within the topic; dump is topic-wide.
const OVERRIDES = [
  { mode: 'quiz', label: 'Quiz' },
  { mode: 'teach', label: 'Teach' },
  { mode: 'ramble', label: 'Ramble' },
  { mode: 'dump', label: 'Brain dump' },
];

interface Props {
  topicId: string;
  courseId?: string;
}

export function NoteStudyPrompt({ topicId, courseId }: Props) {
  const { c, font, size, radius, trackingUtility } = useTheme();
  const [action, setAction] = useState<NextAction | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchNextAction({ topic_id: topicId })
      .then((a) => {
        if (alive) setAction(a);
      })
      .catch(() => {
        if (alive) setAction(null);
      })
      .finally(() => {
        if (alive) setLoaded(true);
      });
    return () => {
      alive = false;
    };
  }, [topicId]);

  // null action means the topic has no concepts yet — nothing to test, so show nothing.
  if (!loaded || !action) return null;

  const launch = (mode: string, useConcept: boolean) => {
    router.push({
      pathname: '/retrieval',
      params: {
        topicId,
        ...(courseId ? { courseId } : {}),
        mode,
        ...(useConcept && action.concept_ids[0] ? { conceptId: action.concept_ids[0] } : {}),
      },
    });
  };

  const utility = {
    fontFamily: font.utility,
    fontSize: size.utility,
    letterSpacing: trackingUtility(size.utility),
    textTransform: 'uppercase' as const,
  };

  return (
    <View style={{ marginTop: 24, borderTopWidth: 1, borderTopColor: c.paperEdge, paddingTop: 20, gap: 14 }}>
      <View style={{ padding: 16, borderWidth: 1, borderColor: c.paperEdge, borderRadius: radius.md, backgroundColor: c.paperRecessed, gap: 6 }}>
        <Text style={[utility, { color: c.stateFading }]}>{ACTION_LEAD[action.kind]}</Text>
        <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink }}>Ready to test yourself?</Text>
        <Text style={{ fontSize: size.bodySm, color: c.inkSecondary }}>{`${action.reason} · about ${action.est_minutes} min`}</Text>
        <Button label={`Start — ${modeLabel(action.mode)}`} onPress={() => launch(action.mode, true)} style={{ marginTop: 10 }} />
      </View>

      <View style={{ gap: 8 }}>
        <Text style={[utility, { color: c.inkTertiary }]}>Or study it your way</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {OVERRIDES.filter((o) => o.mode !== action.mode).map((o) => (
            <Pressable
              key={o.mode}
              onPress={() => launch(o.mode, o.mode !== 'dump')}
              style={{ minHeight: 44, paddingHorizontal: 16, justifyContent: 'center', borderWidth: 1, borderColor: c.paperEdge, borderRadius: radius.md, backgroundColor: c.paper }}
            >
              <Text style={{ fontFamily: font.body, fontSize: 15, color: c.ink }}>{o.label}</Text>
            </Pressable>
          ))}
        </View>
      </View>

      <Pressable
        onPress={() => router.push({ pathname: '/testbuilder', params: { topicId, ...(courseId ? { courseId } : {}) } })}
        style={{ minHeight: 44, justifyContent: 'center' }}
      >
        <Text style={{ fontFamily: font.bodySemibold, fontSize: 15, color: c.confirm }}>✎ Build a practice test</Text>
      </Pressable>
    </View>
  );
}

function modeLabel(mode: string): string {
  const found = OVERRIDES.find((o) => o.mode === mode);
  if (found) return found.label;
  if (mode === 'pretest') return 'Pretest';
  if (mode === 'recap') return 'Recap';
  return 'Review';
}
