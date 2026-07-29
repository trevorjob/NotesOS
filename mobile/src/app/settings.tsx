import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { Chip } from '@/components/ui/Chip';
import { Switch } from '@/components/ui/Switch';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { clearTokens } from '@/lib/auth';
import { Me, changePassword, deleteAccount, fetchMe, updatePersonality, updateProfile } from '@/lib/profile';
import { fetchNotificationPreferences, updateNotificationPreferences } from '@/lib/notifications';

// Chip options carry the backend slug alongside the display label — study_personality
// stores lowercase strings (tone/explanation_style), emoji_usage is a string not a bool.
const TONES = [
  { label: 'Encouraging', value: 'encouraging' },
  { label: 'Direct', value: 'direct' },
  { label: 'Humorous', value: 'humorous' },
];
const STYLES = [
  { label: 'Concise', value: 'concise' },
  { label: 'Detailed', value: 'detailed' },
  { label: 'Example-heavy', value: 'example-heavy' },
];

const MIN_PASSWORD_LENGTH = 8;

function readError(err: unknown): string {
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') return err.response.data.detail;
  return 'Couldn’t save that. Try again.';
}

interface SectionProps {
  label: string;
  children: React.ReactNode;
}

function Section({ label, children }: SectionProps) {
  const { c, font, size, trackingUtility } = useTheme();
  return (
    <View style={{ marginTop: 20 }}>
      <Text
        style={{
          fontFamily: font.utility,
          fontSize: size.caption,
          letterSpacing: trackingUtility(size.caption),
          textTransform: 'uppercase',
          color: c.inkTertiary,
          borderBottomWidth: 1,
          borderBottomColor: c.paperEdge,
          paddingBottom: 8,
          marginBottom: 10,
        }}
      >
        {label}
      </Text>
      {children}
    </View>
  );
}

function Sub({ children }: { children: string }) {
  const { c, size } = useTheme();
  return <Text style={{ fontSize: size.caption, color: c.inkSecondary, marginTop: 10, marginBottom: 6 }}>{children}</Text>;
}

interface ChipRowProps {
  options: { label: string; value: string }[];
  value: string;
  onChange: (value: string) => void;
}

function ChipRow({ options, value, onChange }: ChipRowProps) {
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
      {options.map((o) => (
        <Chip key={o.value} label={o.label} selected={value === o.value} onPress={() => onChange(o.value)} />
      ))}
    </View>
  );
}

interface ToggleRowProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

function ToggleRow({ label, checked, onChange }: ToggleRowProps) {
  const { c, size } = useTheme();
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10, minHeight: 44 }}>
      <Text style={{ color: c.ink, fontSize: size.body }}>{label}</Text>
      <Switch checked={checked} onChange={onChange} />
    </View>
  );
}

interface RowProps {
  children: React.ReactNode;
  onPress?: () => void;
}

function Row({ children, onPress }: RowProps) {
  const { c } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      style={{
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingVertical: 12,
        borderBottomWidth: 1,
        borderBottomColor: c.paperEdge,
        minHeight: 44,
      }}
    >
      {children}
    </Pressable>
  );
}

export default function SettingsScreen() {
  const { c, font, size, space } = useTheme();

  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Tutor personality
  const [tone, setTone] = useState('encouraging');
  const [style, setStyle] = useState('detailed');
  const [emoji, setEmoji] = useState(true);
  // Notifications
  const [digest, setDigest] = useState(true);

  // Name editing
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [nameSaving, setNameSaving] = useState(false);

  // Change password
  const [pwOpen, setPwOpen] = useState(false);
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSaving, setPwSaving] = useState(false);
  const [pwDone, setPwDone] = useState(false);

  // Delete account (soft-delete, reauth with password)
  const [delOpen, setDelOpen] = useState(false);
  const [delPw, setDelPw] = useState('');
  const [delError, setDelError] = useState<string | null>(null);
  const [delSaving, setDelSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [profile, prefs] = await Promise.all([fetchMe(), fetchNotificationPreferences()]);
        if (!alive) return;
        setMe(profile);
        setTone(profile.study_personality?.tone ?? 'encouraging');
        setStyle(profile.study_personality?.explanation_style ?? 'detailed');
        setEmoji((profile.study_personality?.emoji_usage ?? 'moderate') !== 'none');
        setDigest(prefs.digest_enabled);
      } catch (err) {
        if (alive) setLoadError(readError(err));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // Optimistic save: apply locally, persist, roll back the one value on failure.
  const persist = async (fn: () => Promise<void>, revert: () => void) => {
    setSaveError(null);
    try {
      await fn();
    } catch (err) {
      revert();
      setSaveError(readError(err));
    }
  };

  const onTone = (value: string) => {
    const prev = tone;
    setTone(value);
    persist(() => updatePersonality({ tone: value }), () => setTone(prev));
  };
  const onStyle = (value: string) => {
    const prev = style;
    setStyle(value);
    persist(() => updatePersonality({ explanation_style: value }), () => setStyle(prev));
  };
  const onEmoji = (checked: boolean) => {
    const prev = emoji;
    setEmoji(checked);
    persist(() => updatePersonality({ emoji_usage: checked ? 'moderate' : 'none' }), () => setEmoji(prev));
  };
  const onDigest = (checked: boolean) => {
    const prev = digest;
    setDigest(checked);
    persist(() => updateNotificationPreferences({ digest_enabled: checked }), () => setDigest(prev));
  };

  const startEditName = () => {
    setNameDraft(me?.full_name ?? '');
    setEditingName(true);
  };
  const saveName = async () => {
    const trimmed = nameDraft.trim();
    if (!trimmed || !me) return;
    setSaveError(null);
    setNameSaving(true);
    try {
      await updateProfile({ full_name: trimmed });
      setMe({ ...me, full_name: trimmed });
      setEditingName(false);
    } catch (err) {
      setSaveError(readError(err));
    } finally {
      setNameSaving(false);
    }
  };

  const savePassword = async () => {
    setPwError(null);
    if (newPw.length < MIN_PASSWORD_LENGTH) {
      setPwError(`New password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    setPwSaving(true);
    try {
      await changePassword(currentPw, newPw);
      setCurrentPw('');
      setNewPw('');
      setPwOpen(false);
      setPwDone(true);
    } catch (err) {
      setPwError(readError(err));
    } finally {
      setPwSaving(false);
    }
  };

  const signOut = async () => {
    await clearTokens();
    router.replace('/login');
  };

  const confirmDelete = async () => {
    if (!delPw) return;
    setDelError(null);
    setDelSaving(true);
    try {
      await deleteAccount(delPw);
      await clearTokens();
      router.replace('/login');
    } catch (err) {
      setDelError(readError(err));
      setDelSaving(false); // stay on the form; on success we've already navigated away
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10 }}>
        <Pressable onPress={() => router.back()} style={{ minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>← Home</Text>
        </Pressable>
        <Text style={{ fontFamily: font.display, fontSize: size.display2, color: c.ink, marginTop: 4 }}>Settings</Text>
      </View>

      {loading ? (
        <View style={{ paddingTop: 60, alignItems: 'center', gap: 14 }}>
          <ActivityIndicator color={c.ink} />
          <Text style={{ color: c.inkSecondary, fontSize: size.body }}>Loading your settings…</Text>
        </View>
      ) : loadError ? (
        <View style={{ paddingHorizontal: space.gutterPage, paddingTop: 30 }}>
          <Text style={{ color: c.stateShaky, fontSize: size.body }}>{loadError}</Text>
        </View>
      ) : (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 30 }}>
          {saveError && (
            <Text style={{ color: c.stateShaky, fontSize: size.bodySm, marginTop: 12 }}>{saveError}</Text>
          )}

          <Section label="Tutor personality">
            <Sub>Tone</Sub>
            <ChipRow options={TONES} value={tone} onChange={onTone} />
            <Sub>Explanation style</Sub>
            <ChipRow options={STYLES} value={style} onChange={onStyle} />
            <ToggleRow label="Use emoji" checked={emoji} onChange={onEmoji} />
          </Section>

          <Section label="Notifications">
            <ToggleRow label="Daily decay digest" checked={digest} onChange={onDigest} />
            <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>Rare and specific — never a streak reminder.</Text>
          </Section>

          <Section label="Account">
            {editingName ? (
              <View style={{ paddingVertical: 12, gap: 10 }}>
                <Input label="Name" value={nameDraft} onChangeText={setNameDraft} autoFocus />
                <View style={{ flexDirection: 'row', gap: 10 }}>
                  <Button label={nameSaving ? 'Saving…' : 'Save'} size="sm" onPress={saveName} disabled={nameSaving || !nameDraft.trim()} />
                  <Button label="Cancel" size="sm" variant="secondary" onPress={() => setEditingName(false)} disabled={nameSaving} />
                </View>
              </View>
            ) : (
              <Row onPress={startEditName}>
                <Text style={{ color: c.ink }}>Name</Text>
                <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
                  <Text style={{ color: c.inkSecondary }}>{me?.full_name}</Text>
                  <Text style={{ color: c.confirm, fontSize: size.bodySm }}>Edit</Text>
                </View>
              </Row>
            )}

            <Row>
              <Text style={{ color: c.ink }}>Phone</Text>
              <Text style={{ color: c.inkTertiary }}>{me?.phone}</Text>
            </Row>

            {pwOpen ? (
              <View style={{ paddingVertical: 12, gap: 10 }}>
                <Input label="Current password" value={currentPw} onChangeText={setCurrentPw} secureTextEntry />
                <Input label="New password" value={newPw} onChangeText={setNewPw} secureTextEntry error={pwError ?? undefined} />
                <View style={{ flexDirection: 'row', gap: 10 }}>
                  <Button label={pwSaving ? 'Saving…' : 'Update password'} size="sm" onPress={savePassword} disabled={pwSaving || !currentPw || !newPw} />
                  <Button label="Cancel" size="sm" variant="secondary" onPress={() => { setPwOpen(false); setPwError(null); }} disabled={pwSaving} />
                </View>
              </View>
            ) : (
              <Row onPress={() => { setPwOpen(true); setPwDone(false); }}>
                <Text style={{ color: c.confirm, textDecorationLine: 'underline' }}>Change password</Text>
                {pwDone && <Text style={{ color: c.confirm, fontSize: size.bodySm }}>Updated ✓</Text>}
              </Row>
            )}

            <Row onPress={signOut}>
              <Text style={{ color: c.confirm, textDecorationLine: 'underline' }}>Sign out</Text>
            </Row>

            {delOpen ? (
              <View style={{ paddingVertical: 12, gap: 10 }}>
                <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>
                  This wipes your personal details and signs you out for good. Your shared course
                  contributions stay, marked “Former member”. This can’t be undone.
                </Text>
                <Input label="Confirm your password" value={delPw} onChangeText={setDelPw} secureTextEntry error={delError ?? undefined} />
                <View style={{ flexDirection: 'row', gap: 10 }}>
                  <Button label={delSaving ? 'Deleting…' : 'Delete my account'} size="sm" onPress={confirmDelete} disabled={delSaving || !delPw} />
                  <Button label="Cancel" size="sm" variant="secondary" onPress={() => { setDelOpen(false); setDelError(null); setDelPw(''); }} disabled={delSaving} />
                </View>
              </View>
            ) : (
              <Row onPress={() => setDelOpen(true)}>
                <Text style={{ color: c.stateShaky, textDecorationLine: 'underline' }}>Delete account</Text>
              </Row>
            )}
          </Section>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
