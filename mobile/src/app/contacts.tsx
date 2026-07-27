import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Share, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { joinCourse } from '@/lib/courses';
import {
  MatchedContact,
  collectContactHashes,
  getContactsPermission,
  matchContacts,
  requestContactsPermission,
} from '@/lib/contacts';

// "See who you know on NotesOS" — the LAST onboarding beat (after cohort + create
// have already delivered value). Contacts are sensitive, so permission is asked
// with a plain rationale and every stage is skippable. Raw numbers never leave the
// device (lib/contacts hashes locally); we only ever upload hashes.
type Stage = 'rationale' | 'loading' | 'results' | 'denied';

function readError(err: unknown): string {
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') {
    return err.response.data.detail;
  }
  return 'Something went wrong. Try again.';
}

export default function ContactsScreen() {
  const { c, font, size, space } = useTheme();

  const [stage, setStage] = useState<Stage>('rationale');
  const [contacts, setContacts] = useState<MatchedContact[]>([]);
  const [joinedIds, setJoinedIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const finish = () => router.replace('/home');

  const runMatch = async () => {
    setError(null);
    setStage('loading');
    try {
      const hashes = await collectContactHashes();
      setContacts(await matchContacts(hashes));
      setStage('results');
    } catch (err) {
      setError(readError(err));
      setStage('results');
    }
  };

  const handleAllow = async () => {
    const status = await requestContactsPermission();
    if (status === 'granted') {
      runMatch();
    } else {
      setStage('denied');
    }
  };

  const joinContactCourse = async (courseId: string) => {
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

  const inviteFriends = async () => {
    await Share.share({
      message: 'Come study with me on NotesOS — we build the notes together.',
    });
  };

  // If permission was already granted on a prior visit, skip the rationale.
  useEffect(() => {
    let alive = true;
    (async () => {
      const status = await getContactsPermission();
      if (alive && status === 'granted') runMatch();
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
  const bodyStyle = { color: c.inkSecondary, fontSize: size.body };
  const errorText = error ? (
    <Text style={{ color: c.stateShaky, fontSize: size.bodySm }}>{error}</Text>
  ) : null;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <ScrollView contentContainerStyle={{ flexGrow: 1, paddingHorizontal: space.gutterPage, paddingVertical: 40 }}>
        {stage === 'rationale' && (
          <View style={{ gap: 16, flex: 1 }}>
            <Text style={titleStyle}>See who you know on NotesOS</Text>
            <Text style={bodyStyle}>
              We’ll check your contacts against NotesOS and show you which of your friends
              are already here — plus the courses they’re in that you can join.
            </Text>
            <Text style={{ color: c.inkTertiary, fontSize: size.bodySm }}>
              Your contacts stay on your phone. We only send scrambled fingerprints of the
              numbers, never the numbers themselves, and we don’t store anything about
              people who aren’t on NotesOS.
            </Text>
            <View style={{ flex: 1 }} />
            {errorText}
            <Button label="Find my friends" onPress={handleAllow} />
            <Button label="Not now" variant="secondary" onPress={finish} />
          </View>
        )}

        {stage === 'loading' && (
          <View style={{ gap: 16, paddingTop: 60, alignItems: 'center' }}>
            <ActivityIndicator color={c.ink} />
            <Text style={bodyStyle}>Looking for people you know…</Text>
          </View>
        )}

        {stage === 'denied' && (
          <View style={{ gap: 16, flex: 1 }}>
            <Text style={titleStyle}>No problem</Text>
            <Text style={bodyStyle}>
              You can invite friends directly instead — or turn on contacts access later in
              Settings whenever you want.
            </Text>
            <View style={{ flex: 1 }} />
            <Button label="Invite a friend" onPress={inviteFriends} />
            <Button label="Continue to NotesOS" variant="secondary" onPress={finish} />
          </View>
        )}

        {stage === 'results' && (
          <View style={{ gap: 16 }}>
            {contacts.length === 0 ? (
              <>
                <Text style={titleStyle}>You’re early</Text>
                <Text style={bodyStyle}>
                  None of your contacts are on NotesOS yet. Invite a few — studying together
                  is the whole point.
                </Text>
                {errorText}
                <Button label="Invite friends" onPress={inviteFriends} style={{ marginTop: 8 }} />
                <Button label="Continue to NotesOS" variant="secondary" onPress={finish} />
              </>
            ) : (
              <>
                <Text style={titleStyle}>People you know</Text>
                <Text style={bodyStyle}>Join the courses your friends are already building.</Text>

                {contacts.map((contact) => (
                  <View key={contact.id} style={{ paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: c.paperEdge }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                      <Text style={{ fontFamily: font.bodySemibold, color: c.ink, fontSize: size.body }}>
                        {contact.full_name ?? 'A friend'}
                      </Text>
                      {contact.same_school && (
                        <Text style={{ fontSize: size.caption, color: c.confirm }}>· same school</Text>
                      )}
                    </View>

                    {contact.courses.length === 0 ? (
                      <Text style={{ fontSize: size.caption, color: c.inkTertiary, marginTop: 2 }}>
                        On NotesOS
                      </Text>
                    ) : (
                      contact.courses.map((course) => {
                        const joined = joinedIds.includes(course.course_id);
                        return (
                          <View
                            key={course.course_id}
                            style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8, minHeight: 44 }}
                          >
                            <View style={{ flex: 1, paddingRight: 12 }}>
                              <Text style={{ color: c.ink }}>{course.name}</Text>
                              <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>
                                {course.code} · {course.member_count} member{course.member_count === 1 ? '' : 's'}
                              </Text>
                            </View>
                            {joined ? (
                              <Text style={{ color: c.confirm, fontSize: size.bodySm }}>Joined ✓</Text>
                            ) : (
                              <Pressable onPress={() => joinContactCourse(course.course_id)} disabled={submitting} style={{ minHeight: 44, justifyContent: 'center' }}>
                                <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>Join</Text>
                              </Pressable>
                            )}
                          </View>
                        );
                      })
                    )}
                  </View>
                ))}

                {errorText}

                <Button label="Invite more friends" variant="secondary" onPress={inviteFriends} style={{ marginTop: 6 }} />
                <Button label="Done" onPress={finish} />
              </>
            )}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
