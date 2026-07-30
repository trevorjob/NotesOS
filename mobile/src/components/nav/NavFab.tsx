import { router, useGlobalSearchParams } from 'expo-router';
import React, { useCallback, useEffect, useState } from 'react';
import { Animated, Dimensions, PanResponder, Pressable, StyleSheet, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';
import { NextAction, fetchNextAction } from '@/lib/retrieval';

// The engine picks WHAT to study; these let the user override HOW (same topic/concept, other mode).
const OVERRIDE_MODES = [
  { id: 'quiz', label: 'Quiz' },
  { id: 'pretest', label: 'Pretest' },
  { id: 'ramble', label: 'Ramble' },
  { id: 'teach', label: 'Teach' },
  { id: 'recap', label: 'Recap' },
  { id: 'dump', label: 'Brain dump' },
];

// Draggable position + first-run hint persist across route changes (the FAB remounts per route)
// via module state. Cross-restart persistence is a follow-up (needs a storage dep + rebuild).
let savedOffset = { x: 0, y: 0 };
let hintSeen = false;

const DRAG_THRESHOLD = 6;

export function NavFab() {
  const { c, font, radius, hardShadow } = useTheme();
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState<NextAction | null>(null);
  const [showHint, setShowHint] = useState(!hintSeen);

  // On a note (or any topic-scoped route) "study now" should mean what you're reading, not a
  // global concept from another course. Scope the engine pick to the route's topic when present.
  const routeParams = useGlobalSearchParams<{ topicId?: string | string[] }>();
  const scopeTopicId = typeof routeParams.topicId === 'string' ? routeParams.topicId : undefined;

  // Lazy useState (not useRef) for the stable instances/mutable position — reading a ref's
  // .current during render is disallowed, but a state value created once is fine. posBox is a
  // plain mutable box the gesture writes and the handlers read (no re-render needed).
  const [pan] = useState(() => new Animated.ValueXY(savedOffset));
  const [posBox] = useState(() => ({ ...savedOffset }));
  useEffect(() => {
    const id = pan.addListener((v) => {
      posBox.x = v.x;
      posBox.y = v.y;
    });
    return () => pan.removeListener(id);
  }, [pan, posBox]);

  const refresh = useCallback(() => {
    fetchNextAction(scopeTopicId ? { topic_id: scopeTopicId } : undefined)
      .then(setAction)
      .catch(() => setAction(null));
  }, [scopeTopicId]);
  useEffect(() => {
    refresh();
  }, [refresh]);

  const dismissHint = useCallback(() => {
    if (hintSeen) return;
    hintSeen = true;
    setShowHint(false);
  }, []);

  const [panResponder] = useState(() =>
    PanResponder.create({
      onMoveShouldSetPanResponder: (_e, g) => Math.abs(g.dx) > DRAG_THRESHOLD || Math.abs(g.dy) > DRAG_THRESHOLD,
      onPanResponderGrant: () => {
        dismissHint();
        pan.setOffset({ x: posBox.x, y: posBox.y });
        pan.setValue({ x: 0, y: 0 });
      },
      onPanResponderMove: Animated.event([null, { dx: pan.x, dy: pan.y }], { useNativeDriver: false }),
      onPanResponderRelease: () => {
        pan.flattenOffset();
        const { width, height } = Dimensions.get('window');
        // Keep the button on-screen (offsets are relative to the bottom-right anchor).
        const clamped = {
          x: Math.min(0, Math.max(-(width - 60), posBox.x)),
          y: Math.min(20, Math.max(-(height - 140), posBox.y)),
        };
        savedOffset = clamped;
        Animated.spring(pan, { toValue: clamped, useNativeDriver: false, friction: 7 }).start();
      },
    }),
  );

  const launch = (mode: string) => {
    setOpen(false);
    if (!action) return;
    router.push({
      pathname: '/retrieval',
      params: {
        topicId: action.topic_id,
        courseId: action.course_id,
        mode,
        ...(action.concept_ids[0] ? { conceptId: action.concept_ids[0] } : {}),
      },
    });
  };

  const onPrimaryPress = () => {
    dismissHint();
    if (open) {
      setOpen(false);
      return;
    }
    if (action) {
      launch(action.mode); // fast path: engine picks WHAT + HOW
    } else {
      router.push('/courses'); // nothing due → go find something to study
    }
  };

  const onPrimaryLongPress = () => {
    dismissHint();
    refresh();
    setOpen(true);
  };

  return (
    <Animated.View
      style={[styles.root, { transform: pan.getTranslateTransform() }]}
      pointerEvents="box-none"
      {...panResponder.panHandlers}
    >
      {showHint && !open && (
        <View style={[styles.hint, { backgroundColor: c.ink, borderRadius: radius.sm }]}>
          <Text style={{ color: c.paper, fontSize: 12 }}>Tap to study now · hold to choose how</Text>
        </View>
      )}

      {open && (
        <>
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setOpen(false)} />
          <View style={[styles.menu, { backgroundColor: c.paper, borderColor: c.paperEdge, borderRadius: radius.md }, hardShadow(c.paperEdge, 4)]}>
            <View style={[styles.header, { borderBottomColor: c.paperEdge }]}>
              <Text style={{ fontFamily: font.utility, fontSize: 11, letterSpacing: 0.5, textTransform: 'uppercase', color: c.inkTertiary }}>
                {action ? 'Study now' : 'Nothing due'}
              </Text>
              <Text style={{ fontFamily: font.body, fontSize: 13, color: c.inkSecondary, marginTop: 3 }}>
                {action ? action.reason : 'Add material or open a note to start.'}
              </Text>
            </View>

            {action && (
              <>
                <Pressable onPress={() => launch(action.mode)} style={[styles.item, styles.itemBorder, { borderBottomColor: c.paperEdge }]}>
                  <Text style={{ fontFamily: font.bodySemibold, fontSize: 15, color: c.confirm }}>▶ Start — {modeLabel(action.mode)}</Text>
                </Pressable>
                {OVERRIDE_MODES.filter((m) => m.id !== action.mode).map((m) => (
                  <Pressable key={m.id} onPress={() => launch(m.id)} style={styles.item}>
                    <Text style={{ fontFamily: font.body, fontSize: 15, color: c.ink }}>{m.label}</Text>
                  </Pressable>
                ))}
              </>
            )}

            <Pressable
              onPress={() => {
                setOpen(false);
                router.push('/home');
              }}
              style={[styles.item, styles.itemTopBorder, { borderTopColor: c.paperEdge }]}
            >
              <Text style={{ fontFamily: font.body, fontSize: 15, color: c.inkSecondary }}>Home</Text>
            </Pressable>
          </View>
        </>
      )}

      <Pressable
        accessibilityLabel="Study now — tap to start, hold to choose how"
        onPress={onPrimaryPress}
        onLongPress={onPrimaryLongPress}
        delayLongPress={250}
        style={[styles.fab, { backgroundColor: open ? c.paper : c.confirm, borderColor: c.paperEdge }, hardShadow(c.paperEdge, 2)]}
      >
        <Text style={{ fontSize: 18, color: open ? c.ink : c.paper }}>{open ? '×' : '▶'}</Text>
      </Pressable>
    </Animated.View>
  );
}

function modeLabel(mode: string): string {
  return OVERRIDE_MODES.find((m) => m.id === mode)?.label ?? 'Quiz';
}

const styles = StyleSheet.create({
  root: { position: 'absolute', right: 16, bottom: 16, alignItems: 'flex-end' },
  fab: { width: 44, height: 44, borderRadius: 22, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  hint: { position: 'absolute', right: 0, bottom: 54, paddingHorizontal: 12, paddingVertical: 8, maxWidth: 240 },
  menu: { position: 'absolute', right: 0, bottom: 54, borderWidth: 1, overflow: 'hidden', minWidth: 220, maxWidth: 280 },
  header: { paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1 },
  item: { paddingHorizontal: 16, paddingVertical: 10, minHeight: 44, justifyContent: 'center' },
  itemBorder: { borderBottomWidth: 1 },
  itemTopBorder: { borderTopWidth: 1 },
});
