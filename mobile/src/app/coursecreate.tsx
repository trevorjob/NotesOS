import React from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { CourseAcquisition } from '@/components/onboarding/CourseAcquisition';

// The create modal reuses the same cohort→create→proximity→invite flow onboarding
// uses, so there's a single implementation of "get a course in" (native Share invite,
// force-create fallback, join-a-near-match). onDone dismisses back to the course list,
// which refetches on focus.
export default function CourseCreateScreen() {
  const { c, space } = useTheme();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center', paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 4 }}>
          <Pressable onPress={() => router.back()} style={{ minHeight: 44, minWidth: 44, alignItems: 'center', justifyContent: 'center' }}>
            <Text style={{ color: c.inkSecondary, fontSize: 20 }}>✕</Text>
          </Pressable>
        </View>

        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 20 }}>
          <CourseAcquisition onDone={() => router.back()} />
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}
