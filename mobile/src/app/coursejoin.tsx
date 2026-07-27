import React, { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { joinCourse } from '@/lib/courses';

function readError(err: unknown): string {
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') {
    return err.response.data.detail;
  }
  return 'Couldn’t join with that code. Check it and try again.';
}

// Join-by-invite-code modal. The only way into a course you weren't already
// surfaced (cohort/discovery) or created — no public browse (emergent-set model).
export default function CourseJoinScreen() {
  const { c, font, size, space } = useTheme();

  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    const trimmed = code.trim();
    if (!trimmed) return;
    setError(null);
    setSubmitting(true);
    try {
      await joinCourse({ inviteCode: trimmed });
      // Back to the course list, which refetches on focus and shows the new course.
      router.back();
    } catch (err) {
      setError(readError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10 }}>
          <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink }}>Join a course</Text>
          <Pressable onPress={() => router.back()} style={{ minHeight: 44, minWidth: 44, alignItems: 'center', justifyContent: 'center' }}>
            <Text style={{ color: c.inkSecondary, fontSize: 20 }}>✕</Text>
          </Pressable>
        </View>

        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 20 }}>
          <View style={{ gap: 16 }}>
            <Text style={{ color: c.inkSecondary, fontSize: size.body }}>
              Got an invite code from a classmate? Enter it to join their course.
            </Text>

            <Input
              label="Invite code"
              value={code}
              onChangeText={setCode}
              placeholder="e.g. HIST-2F4K"
              autoCapitalize="characters"
              autoFocus
            />

            {error && <Text style={{ color: c.stateShaky, fontSize: size.bodySm }}>{error}</Text>}

            <Button
              label={submitting ? 'Joining…' : 'Join course'}
              onPress={submit}
              disabled={submitting || !code.trim()}
            />
          </View>
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}
