import React, { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Chip } from '@/components/ui/Chip';
import { Switch } from '@/components/ui/Switch';
import { clearTokens } from '@/lib/auth';

const TONES = ['Encouraging', 'Direct', 'Humorous'];
const STYLES = ['Concise', 'Detailed', 'Example-heavy'];

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
  options: string[];
  value: string;
  onChange: (value: string) => void;
}

function ChipRow({ options, value, onChange }: ChipRowProps) {
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
      {options.map((o) => (
        <Chip key={o} label={o} selected={value === o} onPress={() => onChange(o)} />
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
  const [tone, setTone] = useState('Encouraging');
  const [style, setStyle] = useState('Concise');
  const [emoji, setEmoji] = useState(false);
  const [nightJournal, setNightJournal] = useState(false);
  const [digest, setDigest] = useState(true);

  const signOut = async () => {
    await clearTokens();
    router.replace('/login');
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10 }}>
        <Pressable onPress={() => router.back()} style={{ minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>← Home</Text>
        </Pressable>
        <Text style={{ fontFamily: font.display, fontSize: size.display2, color: c.ink, marginTop: 4 }}>Settings</Text>
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 30 }}>
        <Section label="Tutor personality">
          <Sub>Tone</Sub>
          <ChipRow options={TONES} value={tone} onChange={setTone} />
          <Sub>Explanation style</Sub>
          <ChipRow options={STYLES} value={style} onChange={setStyle} />
          <ToggleRow label="Use emoji" checked={emoji} onChange={setEmoji} />
        </Section>

        <Section label="Study">
          <ToggleRow label="Night Journal" checked={nightJournal} onChange={setNightJournal} />
        </Section>

        <Section label="Notifications">
          <ToggleRow label="Daily decay digest" checked={digest} onChange={setDigest} />
          <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>Rare and specific — never a streak reminder.</Text>
        </Section>

        <Section label="Account">
          <Row>
            <Text style={{ color: c.ink }}>Name</Text>
            <Text style={{ color: c.inkSecondary }}>Ada Obi</Text>
          </Row>
          <Row onPress={() => {}}>
            <Text style={{ color: c.confirm, textDecorationLine: 'underline' }}>Change password</Text>
          </Row>
          <Row onPress={signOut}>
            <Text style={{ color: c.confirm, textDecorationLine: 'underline' }}>Sign out</Text>
          </Row>
          <Row onPress={() => router.replace('/login')}>
            <Text style={{ color: c.stateShaky, textDecorationLine: 'underline' }}>Delete account</Text>
          </Row>
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}
