import { router } from 'expo-router';
import React, { useMemo, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';
import { useQuickSwitcher } from './QuickSwitcherContext';

type DirectoryScreen = 'note' | 'topics';

interface DirectoryItem {
  label: string;
  type: 'Note' | 'Course' | 'Topic';
  screen: DirectoryScreen;
  recent?: boolean;
}

const DIRECTORY: DirectoryItem[] = [
  { label: 'Cellular Respiration', type: 'Note', screen: 'note', recent: true },
  { label: 'Organic Chemistry II', type: 'Course', screen: 'topics', recent: true },
  { label: 'Krebs Cycle', type: 'Topic', screen: 'note', recent: true },
  { label: 'Thermodynamics', type: 'Course', screen: 'topics', recent: true },
  { label: 'Cell Biology', type: 'Course', screen: 'topics' },
  { label: 'Photosynthesis', type: 'Topic', screen: 'note' },
  { label: 'Enzyme Kinetics', type: 'Topic', screen: 'note' },
  { label: 'Intro to Statistics', type: 'Course', screen: 'topics' },
];

const SCREEN_ROUTE = { note: '/note', topics: '/topics' } as const satisfies Record<DirectoryScreen, '/note' | '/topics'>;

function DirectoryRow({ item, onSelect }: { item: DirectoryItem; onSelect: (item: DirectoryItem) => void }) {
  const { c, font, size, trackingUtility } = useTheme();
  return (
    <Pressable onPress={() => onSelect(item)} style={[styles.row, { borderBottomColor: c.paperEdge }]}>
      <Text style={{ fontFamily: font.body, fontSize: 16, color: c.ink }}>{item.label}</Text>
      <Text style={{ fontFamily: font.utility, fontSize: size.caption, letterSpacing: trackingUtility(size.caption), textTransform: 'uppercase', color: c.inkTertiary }}>
        {item.type}
      </Text>
    </Pressable>
  );
}

export function QuickSwitcher() {
  const { c, font, size, radius, trackingUtility } = useTheme();
  const { open, closeSwitcher } = useQuickSwitcher();
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => DIRECTORY.filter((r) => r.label.toLowerCase().includes(query.toLowerCase())), [query]);
  const recents = query ? [] : filtered.filter((r) => r.recent);
  const rest = query ? filtered : filtered.filter((r) => !r.recent);

  const select = (item: DirectoryItem) => {
    closeSwitcher();
    setQuery('');
    router.push(SCREEN_ROUTE[item.screen]);
  };

  return (
    <Modal visible={open} transparent animationType="fade" onRequestClose={closeSwitcher}>
      <View style={styles.root}>
        <Pressable style={[StyleSheet.absoluteFill, styles.scrim, { backgroundColor: c.ink }]} onPress={closeSwitcher} />
        <View style={[styles.panel, { backgroundColor: c.paper, borderBottomColor: c.paperEdge }]}>
          <TextInput
            autoFocus
            placeholder="Jump to any course, topic, or note"
            placeholderTextColor={c.inkTertiary}
            value={query}
            onChangeText={setQuery}
            style={[styles.search, { borderColor: c.paperEdge, borderRadius: radius.sm, backgroundColor: c.paper, color: c.ink }]}
          />
          <ScrollView>
            {recents.length > 0 && (
              <>
                <Text style={[styles.label, { fontFamily: font.utility, fontSize: size.caption, letterSpacing: trackingUtility(size.caption), color: c.inkTertiary }]}>
                  Recents
                </Text>
                {recents.map((r, i) => (
                  <DirectoryRow key={`recent-${i}`} item={r} onSelect={select} />
                ))}
              </>
            )}
            <Text style={[styles.label, { fontFamily: font.utility, fontSize: size.caption, letterSpacing: trackingUtility(size.caption), color: c.inkTertiary, marginTop: recents.length ? 20 : 0 }]}>
              {query ? 'Results' : 'All courses & topics'}
            </Text>
            {rest.map((r, i) => (
              <DirectoryRow key={`rest-${i}`} item={r} onSelect={select} />
            ))}
            {filtered.length === 0 && (
              <Text style={{ color: c.inkTertiary, fontSize: size.bodySm, paddingVertical: 12 }}>Nothing matches &ldquo;{query}&rdquo;</Text>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  scrim: { opacity: 0.3 },
  panel: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderBottomWidth: 1, padding: 20, paddingTop: 60 },
  search: { fontSize: 16, paddingHorizontal: 14, paddingVertical: 12, marginBottom: 14, borderWidth: 1, minHeight: 44 },
  label: { textTransform: 'uppercase', marginBottom: 8 },
  row: { paddingVertical: 12, borderBottomWidth: 1, minHeight: 44, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
});
