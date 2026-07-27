import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, Share, Text, View } from 'react-native';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  CohortCourse,
  CreatedCourse,
  ProximityMatch,
  createCourse,
  fetchCohortCourses,
  joinCourse,
} from '@/lib/courses';

// The onboarding "get your courses in" phase, built to prevent duplicate creation:
// cohort first (join what's already there), create only as a fallback (proximity
// check catches near-dupes), then invite classmates to a freshly created course.
type Stage = 'cohort' | 'create' | 'invite';

interface CourseAcquisitionProps {
  onDone: () => void;
}

function readError(err: unknown): string {
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') {
    return err.response.data.detail;
  }
  return 'Something went wrong. Try again.';
}

export function CourseAcquisition({ onDone }: CourseAcquisitionProps) {
  const { c, font, size } = useTheme();

  const [stage, setStage] = useState<Stage>('cohort');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [cohort, setCohort] = useState<CohortCourse[]>([]);
  const [joinedIds, setJoinedIds] = useState<string[]>([]);

  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [matches, setMatches] = useState<ProximityMatch[] | null>(null);
  const [created, setCreated] = useState<CreatedCourse | null>(null);

  // Fetch the cohort once. Empty cohort → skip straight to create (nothing to join).
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const courses = await fetchCohortCourses();
        if (!alive) return;
        setCohort(courses);
        setStage(courses.length ? 'cohort' : 'create');
      } catch (err) {
        if (alive) setError(readError(err));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const titleStyle = {
    fontFamily: font.display,
    fontSize: size.display1,
    lineHeight: size.display1 * 1.15,
    color: c.ink,
  };
  const errorText = error ? (
    <Text style={{ color: c.stateShaky, fontSize: size.bodySm }}>{error}</Text>
  ) : null;

  const joinCohortCourse = async (courseId: string) => {
    setError(null);
    setSubmitting(true);
    try {
      await joinCourse({ courseId });
      setJoinedIds((prev) => [...prev, courseId]);
    } catch (err) {
      setError(readError(err));
    } finally {
      setSubmitting(false);
    }
  };

  const submitCreate = async (force: boolean) => {
    if (!code.trim() || !name.trim()) return;
    setError(null);
    setSubmitting(true);
    try {
      const result = await createCourse({ code: code.trim(), name: name.trim(), force });
      if (result.kind === 'proximity') {
        setMatches(result.matches);
      } else {
        setCreated(result.course);
        setStage('invite');
      }
    } catch (err) {
      setError(readError(err));
    } finally {
      setSubmitting(false);
    }
  };

  const joinProximityMatch = async (courseId: string) => {
    setError(null);
    setSubmitting(true);
    try {
      await joinCourse({ courseId });
      onDone();
    } catch (err) {
      setError(readError(err));
    } finally {
      setSubmitting(false);
    }
  };

  const shareInvite = async () => {
    if (!created) return;
    const link = created.share_link ?? created.invite_code ?? '';
    await Share.share({
      message: `Join me on NotesOS — ${created.name}. ${link}`.trim(),
    });
  };

  if (loading) {
    return (
      <View style={{ gap: 16, paddingTop: 40, alignItems: 'center' }}>
        <ActivityIndicator color={c.ink} />
        <Text style={{ color: c.inkSecondary, fontSize: size.body }}>Finding your courses…</Text>
      </View>
    );
  }

  if (stage === 'cohort') {
    return (
      <View style={{ gap: 16 }}>
        <Text style={titleStyle}>Your classmates are already here</Text>
        <Text style={{ color: c.inkSecondary, fontSize: size.body }}>
          Active courses in your school, year and program. Join the ones you take.
        </Text>

        {cohort.map((course) => {
          const joined = joinedIds.includes(course.course_id);
          const peers = course.signals.cohort_peers_here;
          return (
            <View
              key={course.course_id}
              style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: c.paperEdge, minHeight: 44 }}
            >
              <View style={{ flex: 1, paddingRight: 12 }}>
                <Text style={{ fontWeight: '600', color: c.ink }}>{course.name}</Text>
                <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>
                  {course.code}
                  {peers > 0 ? ` · ${peers} classmate${peers > 1 ? 's' : ''} here` : ''}
                </Text>
              </View>
              {joined ? (
                <Text style={{ color: c.confirm, fontSize: size.bodySm }}>Joined ✓</Text>
              ) : (
                <Pressable onPress={() => joinCohortCourse(course.course_id)} disabled={submitting} style={{ minHeight: 44, justifyContent: 'center' }}>
                  <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>Join</Text>
                </Pressable>
              )}
            </View>
          );
        })}

        {errorText}

        <Button
          label={joinedIds.length ? 'Continue' : 'Skip for now'}
          onPress={onDone}
          disabled={submitting}
          style={{ marginTop: 6 }}
        />
        <Button label="Create your own course" variant="secondary" onPress={() => setStage('create')} disabled={submitting} />
      </View>
    );
  }

  if (stage === 'create') {
    return (
      <View style={{ gap: 16 }}>
        <Text style={titleStyle}>Create a course</Text>
        <Text style={{ color: c.inkSecondary, fontSize: size.body }}>
          Give it a code and a name. We’ll check if one already exists at your school.
        </Text>

        <Input label="Course code" value={code} onChangeText={setCode} placeholder="e.g. BIO 204" autoCapitalize="characters" />
        <Input label="Course name" value={name} onChangeText={setName} placeholder="e.g. Cell Biology" />

        {matches && matches.length > 0 && (
          <View style={{ gap: 12, marginTop: 4 }}>
            <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>
              These look close — join one, or make your own anyway.
            </Text>
            {matches.map((match) => (
              <View key={match.course_id} style={{ paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: c.paperEdge }}>
                <Text style={{ fontWeight: '600', color: c.ink }}>{match.name}</Text>
                <Text style={{ fontSize: size.caption, color: c.inkTertiary, marginBottom: 8 }}>
                  {match.code} · {match.member_count} member{match.member_count === 1 ? '' : 's'}
                  {match.signals.same_program > 0 ? ' · same program' : ''}
                </Text>
                <Pressable onPress={() => joinProximityMatch(match.course_id)} disabled={submitting} style={{ minHeight: 44, justifyContent: 'center' }}>
                  <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>Join this one</Text>
                </Pressable>
              </View>
            ))}
          </View>
        )}

        {errorText}

        {matches ? (
          <Button
            label={submitting ? 'Creating…' : 'Make my own anyway'}
            variant="secondary"
            onPress={() => submitCreate(true)}
            disabled={submitting}
          />
        ) : (
          <Button
            label={submitting ? 'Checking…' : 'Continue'}
            onPress={() => submitCreate(false)}
            disabled={submitting || !code.trim() || !name.trim()}
          />
        )}

        {cohort.length > 0 && (
          <Pressable onPress={() => { setMatches(null); setStage('cohort'); }} disabled={submitting} style={{ minHeight: 44, justifyContent: 'center', alignItems: 'center' }}>
            <Text style={{ color: c.inkTertiary, fontSize: size.bodySm }}>← Back to your classmates’ courses</Text>
          </Pressable>
        )}
      </View>
    );
  }

  // stage === 'invite'
  return (
    <View style={{ gap: 16 }}>
      <Text style={titleStyle}>You created {created?.name}</Text>
      <Text style={{ color: c.inkSecondary, fontSize: size.body }}>
        Invite your classmates so the notes build together.
      </Text>

      {created?.invite_code && (
        <View style={{ borderWidth: 1, borderColor: c.paperEdge, borderRadius: 2, paddingVertical: 16, alignItems: 'center' }}>
          <Text style={{ fontFamily: font.utility, fontSize: size.caption, color: c.inkTertiary, textTransform: 'uppercase' }}>
            Invite code
          </Text>
          <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink, marginTop: 4 }}>
            {created.invite_code}
          </Text>
        </View>
      )}

      {errorText}

      <Button label="Share invite" onPress={shareInvite} />
      <Button label="Done" variant="secondary" onPress={onDone} />
    </View>
  );
}
