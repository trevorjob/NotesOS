import React, { useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { router } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { fetchWeakConcepts, WeakConcept } from '@/lib/audio';

interface WeakConceptSuggestionProps {
  topicId?: string;
  courseId?: string;
}

// "You keep missing X, want a breakdown?" (docs/listen-audio-plan.md §6) — surfaces the
// caller's single shakiest concept in a topic and routes to a targeted, personal
// remediation lesson. Shared between note.tsx and listen.tsx (topic mode). Silent on
// fetch failure or no candidates — this is a suggestion, never a hard dependency.
export function WeakConceptSuggestion({ topicId, courseId }: WeakConceptSuggestionProps) {
  const { c, size, radius, space } = useTheme();
  const [concept, setConcept] = useState<WeakConcept | null>(null);

  useEffect(() => {
    if (!topicId) return;
    let alive = true;
    fetchWeakConcepts(topicId)
      .then((concepts) => {
        if (alive) setConcept(concepts[0] ?? null);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [topicId]);

  if (!concept) return null;

  return (
    <View
      style={{
        marginHorizontal: space.gutterPage,
        marginTop: 14,
        padding: 14,
        borderRadius: radius.md,
        borderWidth: 1,
        borderColor: c.paperEdge,
        backgroundColor: c.paperRecessed,
        gap: 10,
      }}
    >
      <Text style={{ fontSize: size.bodySm, color: c.ink }}>
        {`You keep missing "${concept.term}" — want a breakdown?`}
      </Text>
      <Button
        label="Generate audio"
        size="sm"
        variant="secondary"
        onPress={() =>
          router.push({
            pathname: '/listen',
            params: {
              conceptId: concept.concept_id,
              conceptTerm: concept.term,
              topicId,
              courseId,
              lens: 'remediation',
            },
          })
        }
      />
    </View>
  );
}
