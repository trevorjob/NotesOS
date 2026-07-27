import { router } from 'expo-router';
import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

const RETRIEVAL_MODES = [
  { id: 'quiz', label: 'Quiz' },
  { id: 'pretest', label: 'Pretest' },
  { id: 'ramble', label: 'Ramble' },
  { id: 'teach', label: 'Teach' },
  { id: 'recap', label: 'Recap' },
  { id: 'dump', label: 'Brain dump' },
  { id: 'test', label: 'Timed test' },
];

export function NavFab() {
  const { c, font, radius, hardShadow } = useTheme();
  const [open, setOpen] = useState(false);

  const goHome = () => {
    setOpen(false);
    router.push('/home');
  };
  const goMode = (mode: string) => {
    setOpen(false);
    router.push({ pathname: '/retrieval', params: { mode } });
  };

  return (
    <View style={styles.root} pointerEvents="box-none">
      {open && (
        <>
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setOpen(false)} />
          <View style={[styles.menu, { backgroundColor: c.paper, borderColor: c.paperEdge, borderRadius: radius.md }, hardShadow(c.paperEdge, 4)]}>
            <Pressable onPress={goHome} style={[styles.item, styles.itemBorder, { borderBottomColor: c.paperEdge }]}>
              <Text style={{ fontFamily: font.bodySemibold, fontSize: 15, color: c.ink }}>Home</Text>
            </Pressable>
            {RETRIEVAL_MODES.map((m) => (
              <Pressable key={m.id} onPress={() => goMode(m.id)} style={styles.item}>
                <Text style={{ fontFamily: font.body, fontSize: 15, color: c.ink }}>{m.label}</Text>
              </Pressable>
            ))}
          </View>
        </>
      )}
      <Pressable
        accessibilityLabel="Go home or start a retrieval mode"
        onPress={() => setOpen((o) => !o)}
        style={[styles.fab, { backgroundColor: c.paper, borderColor: c.paperEdge }, hardShadow(c.paperEdge, 2)]}
      >
        <Text style={{ fontSize: 18, color: c.ink }}>{open ? '×' : '☰'}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { position: 'absolute', right: 16, bottom: 16, alignItems: 'flex-end' },
  fab: { width: 44, height: 44, borderRadius: 22, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  menu: { position: 'absolute', right: 0, bottom: 54, borderWidth: 1, overflow: 'hidden', minWidth: 160 },
  item: { paddingHorizontal: 16, paddingVertical: 10, minHeight: 44, justifyContent: 'center' },
  itemBorder: { borderBottomWidth: 1 },
});
