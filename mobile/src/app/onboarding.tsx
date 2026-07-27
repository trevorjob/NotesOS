import React, { useEffect, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Chip } from '@/components/ui/Chip';
import { Input } from '@/components/ui/Input';
import { CourseAcquisition } from '@/components/onboarding/CourseAcquisition';
import { api } from '@/lib/api';

const YEARS = ['2023', '2024', '2025', '2026', '2027'];
const STEPS = ['school', 'profile', 'courses', 'done'] as const;
type Step = (typeof STEPS)[number];

interface SchoolResult {
  id: string;
  name: string;
  country?: string | null;
}

interface SchoolOption {
  label: string;
  value: string;
}

function readError(err: unknown): string {
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') {
    return err.response.data.detail;
  }
  return 'Something went wrong. Try again.';
}

function UtilityLabel({ children, muted }: { children: string; muted?: boolean }) {
  const { c, font, size, trackingUtility } = useTheme();
  return (
    <Text
      style={{
        fontFamily: font.utility,
        fontSize: size.utility,
        letterSpacing: trackingUtility(size.utility),
        textTransform: 'uppercase',
        color: muted ? c.inkTertiary : c.inkSecondary,
      }}
    >
      {children}
    </Text>
  );
}

function Progress({ step }: { step: Step }) {
  const { c, radius } = useTheme();
  const i = STEPS.indexOf(step);
  return (
    <View style={{ flexDirection: 'row', gap: 6, marginBottom: 28 }}>
      {STEPS.map((s, si) => (
        <View
          key={s}
          style={{ flex: 1, height: 3, borderRadius: radius.pill, backgroundColor: si <= i ? c.ink : c.paperEdge }}
        />
      ))}
    </View>
  );
}

export default function OnboardingFlow() {
  const { c, font, size, space } = useTheme();
  const [step, setStep] = useState<Step>('school');
  const [schoolQuery, setSchoolQuery] = useState('');
  const [school, setSchool] = useState('');
  const [schoolResults, setSchoolResults] = useState<SchoolResult[]>([]);
  const [field, setField] = useState('');
  const [year, setYear] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Live school typeahead. Debounced; skips when a school is already selected.
  // A failed lookup is non-fatal — the "use as typed" fallback still lets the
  // user proceed, and the server canonicalises/creates the school on write.
  useEffect(() => {
    const q = schoolQuery.trim();
    if (!q || q === school) {
      setSchoolResults([]);
      return;
    }
    const handle = setTimeout(async () => {
      try {
        const { data } = await api.get('/api/schools/search', { params: { q } });
        setSchoolResults(data.schools ?? []);
      } catch {
        setSchoolResults([]);
      }
    }, 300);
    return () => clearTimeout(handle);
  }, [schoolQuery, school]);

  const schoolOptions: SchoolOption[] = schoolResults.length
    ? schoolResults.map((s) => ({ label: s.name, value: s.name }))
    : schoolQuery.trim()
      ? [{ label: `Use "${schoolQuery.trim()}" as typed`, value: schoolQuery.trim() }]
      : [];

  // Save school + profile signals, then advance into the course-acquisition phase.
  // School is required (collected in the previous step); program/year are optional.
  // Both "Continue" and "Skip" land here so the school is always persisted.
  const saveProfileAndContinue = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await api.patch('/api/auth/me', {
        school_name: school,
        program: field.trim() || null,
        entry_year: year ? Number(year) : null,
      });
      setStep('courses');
    } catch (err) {
      setError(readError(err));
    } finally {
      setSubmitting(false);
    }
  };

  // The final onboarding beat — "see who you know on NotesOS" — runs after value
  // is delivered (cohort/create done). It's its own screen so it can be reached
  // from home later too; skipping it lands straight on home.
  const goToContacts = () => router.replace('/contacts');
  const skipToHome = () => router.replace('/home');

  const titleStyle = { fontFamily: font.display, fontSize: size.display1, lineHeight: size.display1 * 1.15, color: c.ink };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <ScrollView contentContainerStyle={{ flexGrow: 1, paddingHorizontal: space.gutterPage, paddingVertical: 40 }}>
        <Progress step={step} />

        {step === 'school' && (
          <View style={{ gap: 16 }}>
            <Text style={titleStyle}>Which school are you at?</Text>
            <Text style={{ color: c.inkSecondary, fontSize: size.body }}>
              This tells us which courses and classmates to show you.
            </Text>
            <Input
              autoFocus
              placeholder="Search your school"
              value={schoolQuery}
              onChangeText={(v) => {
                setSchoolQuery(v);
                setSchool('');
              }}
            />
            {schoolQuery.length > 0 && !school && schoolOptions.length > 0 && (
              <View style={{ borderWidth: 1, borderColor: c.paperEdge, borderRadius: 2 }}>
                {schoolOptions.map((opt, i) => (
                  <Pressable
                    key={i}
                    onPress={() => {
                      setSchool(opt.value);
                      setSchoolQuery(opt.value);
                    }}
                    style={{
                      minHeight: 44,
                      justifyContent: 'center',
                      paddingHorizontal: 14,
                      paddingVertical: 10,
                      borderBottomWidth: 1,
                      borderBottomColor: c.paperEdge,
                    }}
                  >
                    <Text style={{ fontSize: 15, color: c.ink }}>{opt.label}</Text>
                  </Pressable>
                ))}
              </View>
            )}
            <Button label="Continue" disabled={!school} onPress={() => setStep('profile')} />
          </View>
        )}

        {step === 'profile' && (
          <View style={{ gap: 16 }}>
            <Text style={titleStyle}>A little more about you</Text>
            <View style={{ gap: 6 }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                <UtilityLabel>Major or field of study</UtilityLabel>
                <UtilityLabel muted>Optional</UtilityLabel>
              </View>
              <Input value={field} onChangeText={setField} placeholder="e.g. Biochemistry" />
            </View>
            <View style={{ gap: 8 }}>
              <UtilityLabel>Year of entry</UtilityLabel>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                {YEARS.map((y) => (
                  <Chip key={y} label={y} selected={year === y} onPress={() => setYear(y)} />
                ))}
              </View>
            </View>
            {error && <Text style={{ color: c.stateShaky, fontSize: size.bodySm }}>{error}</Text>}
            <Button
              label={submitting ? 'Saving…' : 'Continue'}
              disabled={submitting}
              onPress={saveProfileAndContinue}
            />
            <Pressable
              onPress={saveProfileAndContinue}
              disabled={submitting}
              style={{ minHeight: 44, justifyContent: 'center', alignItems: 'center' }}
            >
              <Text style={{ color: c.inkTertiary, fontSize: size.bodySm }}>Skip</Text>
            </Pressable>
          </View>
        )}

        {step === 'courses' && <CourseAcquisition onDone={() => setStep('done')} />}

        {step === 'done' && (
          <View style={{ flex: 1, justifyContent: 'center', gap: 16 }}>
            <Text style={{ fontFamily: font.display, fontSize: size.display2, color: c.ink }}>You’re all set.</Text>
            <Text style={{ color: c.inkSecondary, fontSize: size.body }}>
              {school}{field ? ' · ' + field : ''} — your courses are ready when you are.
              One last thing: see which of your friends are already here.
            </Text>
            <Button label="See who you know" onPress={goToContacts} />
            <Button label="Skip to NotesOS" variant="secondary" onPress={skipToHome} />
            <View style={{ height: space.gutterPage }} />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
