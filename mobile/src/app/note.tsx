import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { Textarea } from '@/components/ui/Textarea';
import { useQuickSwitcher } from '@/components/nav/QuickSwitcherContext';
import { AITutorChat } from '@/components/note/AITutorChat';
import { buildConceptIndex, LitText, NoteMarkdown } from '@/components/note/NoteMarkdown';
import { stateColor, stateLabel } from '@/components/note/mastery';
import { WeakConceptSuggestion } from '@/components/note/WeakConceptSuggestion';
import { NoteStudyPrompt } from '@/components/note/NoteStudyPrompt';
import { ReportSheet } from '@/components/report/ReportSheet';
import { CourseTopic, fetchCourseTopics } from '@/lib/topics';
import {
  ConceptMastery,
  ConceptStates,
  fetchConceptStates,
  fetchTopicContributions,
  fetchTopicHeader,
  fetchTopicKnowledge,
  MasteryState,
  regenerateKnowledge,
  TopicContributions,
  TopicHeader,
  TopicKnowledge,
} from '@/lib/note';

interface SheetSelection {
  concept: string;
  conceptId: string;
  state: MasteryState;
  definition: string | null;
}

function PagerButton({ dir, onPress }: { dir: 'prev' | 'next'; onPress: () => void }) {
  const { c, radius } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityLabel={dir === 'prev' ? 'Previous topic' : 'Next topic'}
      hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
      style={{ width: 36, height: 36, flexShrink: 0, borderWidth: 1, borderColor: c.paperEdge, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' }}
    >
      <Text style={{ color: c.inkSecondary, fontSize: 16 }}>{dir === 'prev' ? '‹' : '›'}</Text>
    </Pressable>
  );
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const days = Math.floor((Date.now() - then) / 86_400_000);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days} days ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// The header attribution beat: what's new since you last read, else the latest contribution,
// else a plain "updated" fallback. Null when there's nothing real to say.
function attributionLine(contrib: TopicContributions | null, generatedAt: string | null): string | null {
  if (contrib?.new_since_last_read && contrib.new_since_last_read > 0) {
    const n = contrib.new_since_last_read;
    return `${n} new ${n === 1 ? 'addition' : 'additions'} since you last read`;
  }
  const latest = contrib?.recent[0];
  if (latest) return `${latest.uploader_name} added “${latest.title}” · ${relativeTime(latest.created_at)}`;
  if (generatedAt) return `Updated ${relativeTime(generatedAt)}`;
  return null;
}

function contributorLine(contrib: TopicContributions | null): string | null {
  if (!contrib || contrib.contributor_count === 0) return null;
  const names = contrib.contributors.map((x) => x.name);
  if (names.length === 1) return `Built by ${names[0]}`;
  if (names.length === 2) return `Built by ${names[0]} & ${names[1]}`;
  return `Built by ${names[0]}, ${names[1]} & ${contrib.contributor_count - 2} ${contrib.contributor_count - 2 === 1 ? 'other' : 'others'}`;
}

function Rule({ label }: { label?: string }) {
  const { c, font, size, space, trackingUtility } = useTheme();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: space[6], marginBottom: space[4] }}>
      <View style={{ flex: label ? 0 : 1, width: label ? 16 : undefined, borderTopWidth: 1, borderTopColor: c.paperEdge }} />
      {label ? (
        <Text style={{ fontFamily: font.utility, fontSize: size.caption, letterSpacing: trackingUtility(size.caption), textTransform: 'uppercase', color: c.inkTertiary }}>
          {label}
        </Text>
      ) : null}
      <View style={{ flex: 1, borderTopWidth: 1, borderTopColor: c.paperEdge }} />
    </View>
  );
}

function TrustLink({ label, color, onPress }: { label: string; color: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={{ minHeight: 44, justifyContent: 'center' }}>
      <Text style={{ color, textDecorationLine: 'underline', fontSize: 13 }}>{label}</Text>
    </Pressable>
  );
}

export default function NoteScreen() {
  const { c, font, size, space, radius, trackingUtility } = useTheme();
  const { topicId, courseId } = useLocalSearchParams<{ topicId?: string; courseId?: string }>();
  const { openSwitcher } = useQuickSwitcher();

  const [header, setHeader] = useState<TopicHeader | null>(null);
  const [knowledge, setKnowledge] = useState<TopicKnowledge | null>(null);
  const [states, setStates] = useState<ConceptStates | null>(null);
  const [contributions, setContributions] = useState<TopicContributions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [siblings, setSiblings] = useState<CourseTopic[]>([]);
  const [courseName, setCourseName] = useState<string | null>(null);

  const [sheet, setSheet] = useState<SheetSelection | null>(null);
  const [showReport, setShowReport] = useState(false);
  const [showProvenance, setShowProvenance] = useState(false);
  const [showTutor, setShowTutor] = useState(false);

  const load = useCallback(async () => {
    if (!topicId) {
      setError('No topic selected.');
      setLoading(false);
      return;
    }
    try {
      setError(null);
      const [h, k, s, contrib] = await Promise.all([
        fetchTopicHeader(topicId),
        fetchTopicKnowledge(topicId),
        fetchConceptStates(topicId),
        fetchTopicContributions(topicId).catch(() => null),
      ]);
      setHeader(h);
      setKnowledge(k);
      setStates(s);
      setContributions(contrib);
    } catch {
      setError('Could not load this note. Pull to retry.');
    } finally {
      setLoading(false);
    }
  }, [topicId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  // Sibling topics (for the prev/next pager + breadcrumb) are course-scoped, so they load
  // once per course and stay put while paging between topics — the header never flickers.
  useEffect(() => {
    if (!courseId) return;
    let alive = true;
    fetchCourseTopics(courseId)
      .then((detail) => {
        if (!alive) return;
        setSiblings(detail.topics);
        setCourseName(detail.course.name);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [courseId]);

  const currentIndex = useMemo(() => siblings.findIndex((t) => t.id === topicId), [siblings, topicId]);
  const canPage = siblings.length > 1 && currentIndex >= 0;
  const goToTopic = (delta: number) => {
    if (!canPage) return;
    const next = siblings[(currentIndex + delta + siblings.length) % siblings.length];
    router.setParams({ topicId: next.id });
  };

  const launchConcept = (concept: ConceptMastery) =>
    setSheet({ concept: concept.term, conceptId: concept.concept_id, state: concept.state, definition: concept.definition });

  const startRetrieval = () => {
    if (!sheet) return;
    const { concept, conceptId, state } = sheet;
    setSheet(null);
    router.push({ pathname: '/retrieval', params: { concept, conceptId, conceptState: state, topicId, courseId } });
  };

  const explainConceptMyWay = (instruction: string) => {
    if (!sheet) return;
    const { concept, conceptId } = sheet;
    setSheet(null);
    router.push({
      pathname: '/listen',
      params: { conceptId, conceptTerm: concept, instruction, topicId, courseId },
    });
  };

  const conceptIndex = useMemo(() => buildConceptIndex(states?.concepts ?? []), [states]);

  // Prefer the sibling title (stable + instant on paging) over the per-topic fetch.
  const title = siblings[currentIndex]?.title ?? header?.title ?? 'Note';
  const note = knowledge?.consolidated_note?.trim() || null;
  const status = knowledge?.status ?? 'pending';
  const attribution = attributionLine(contributions, knowledge?.generated_at ?? knowledge?.updated_at ?? null);
  const builtBy = contributorLine(contributions);
  const isEmpty = knowledge != null && knowledge.source_count === 0;
  const isSynthesizing = !isEmpty && !note && (status === 'pending' || status === 'processing');
  const isFailed = status === 'failed' && !note;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
        <View style={{ padding: 20, paddingTop: 18, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: c.paperEdge }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
            <Text style={{ fontFamily: font.utility, fontSize: size.caption, letterSpacing: trackingUtility(size.caption), textTransform: 'uppercase', color: c.inkTertiary }}>
              {courseName ?? (header?.week_number ? `Week ${header.week_number}` : 'Consolidated note')}
            </Text>
            <Pressable
              onPress={openSwitcher}
              accessibilityLabel="Switch"
              style={{ width: 44, height: 44, borderWidth: 1, borderColor: c.paperEdge, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}
            >
              <Text style={{ color: c.ink, fontSize: 16 }}>⌕</Text>
            </Pressable>
          </View>

          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            {canPage && <PagerButton dir="prev" onPress={() => goToTopic(-1)} />}
            <Text style={{ flex: 1, fontFamily: font.display, fontSize: size.display2, lineHeight: size.display2 * 1.15, textAlign: canPage ? 'center' : 'left', color: c.ink }}>
              {title}
            </Text>
            {canPage && <PagerButton dir="next" onPress={() => goToTopic(1)} />}
          </View>

          {canPage && (
            <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 6, marginTop: 8 }}>
              {siblings.map((t, i) => (
                <View key={t.id} style={{ width: 5, height: 5, borderRadius: 2.5, backgroundColor: i === currentIndex ? c.ink : c.paperEdge }} />
              ))}
            </View>
          )}

          {note && attribution && (
            <View style={{ marginTop: 10, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: c.confirm }} />
              <Text style={{ flex: 1, fontFamily: font.utility, fontSize: size.utility, color: c.confirm }}>
                {attribution}
              </Text>
            </View>
          )}
        </View>

        {loading ? (
          <View style={{ paddingVertical: 64, alignItems: 'center' }}>
            <ActivityIndicator color={c.ink} />
          </View>
        ) : error ? (
          <View style={{ paddingVertical: 48, paddingHorizontal: 20, alignItems: 'center', gap: 12 }}>
            <Text style={{ color: c.inkSecondary, fontSize: size.body, textAlign: 'center' }}>{error}</Text>
            <Button label="Try again" variant="secondary" onPress={load} />
          </View>
        ) : (
          <>
            {(note || isSynthesizing) && (
              <View style={{ flexDirection: 'row', gap: 10, paddingHorizontal: 20, paddingTop: 14 }}>
                <Button label="Ask the tutor" variant="secondary" icon={<Text style={{ color: c.ink }}>◎</Text>} onPress={() => setShowTutor(true)} style={{ flex: 1 }} />
                <Button label="Listen" variant="secondary" icon={<Text style={{ color: c.ink }}>♫</Text>} onPress={() => router.push({ pathname: '/listen', params: { topicId, courseId } })} style={{ flex: 1 }} />
              </View>
            )}

            {note && <WeakConceptSuggestion topicId={topicId} courseId={courseId} />}

            <View style={{ paddingHorizontal: 20 }}>
              {isEmpty ? (
                <View style={{ paddingVertical: 48, alignItems: 'center', gap: 12 }}>
                  <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink }}>Nothing here yet</Text>
                  <Text style={{ color: c.inkSecondary, fontSize: size.bodySm, maxWidth: 260, textAlign: 'center' }}>
                    This topic is scaffolded but has no material. Add something to get a note started.
                  </Text>
                  <Button label="Add material" variant="text" onPress={() => router.push({ pathname: '/capture', params: { courseId } })} />
                </View>
              ) : isFailed ? (
                <View style={{ paddingVertical: 48, alignItems: 'center', gap: 12 }}>
                  <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink }}>Synthesis hit a snag</Text>
                  <Text style={{ color: c.inkSecondary, fontSize: size.bodySm, maxWidth: 280, textAlign: 'center' }}>
                    {knowledge?.error_message || 'The note could not be built from the current material.'}
                  </Text>
                  <Button
                    label="Rebuild the note"
                    variant="secondary"
                    onPress={async () => {
                      if (topicId) await regenerateKnowledge(topicId);
                      load();
                    }}
                  />
                </View>
              ) : isSynthesizing ? (
                <View style={{ paddingVertical: 32, gap: 14 }}>
                  <Text style={{ fontFamily: font.utility, fontSize: size.utility, letterSpacing: trackingUtility(size.utility), textTransform: 'uppercase', color: c.stateFading }}>
                    Synthesizing — writing itself in
                  </Text>
                  {[92, 78, 85, 60].map((w, i) => (
                    <View key={i} style={{ height: 14, width: `${w}%`, backgroundColor: c.paperRecessed, borderRadius: radius.sm }} />
                  ))}
                </View>
              ) : note ? (
                <>
                  <View style={{ marginTop: 6 }}>
                    <NoteMarkdown value={note} index={conceptIndex} onLaunch={launchConcept} />
                  </View>

                  {knowledge && knowledge.key_points.length > 0 && (
                    <>
                      <Rule label="Key points" />
                      <View style={{ gap: 8 }}>
                        {knowledge.key_points.map((kp, i) => (
                          <View key={i} style={{ flexDirection: 'row', gap: 8 }}>
                            <Text style={{ color: c.inkTertiary }}>•</Text>
                            <LitText
                              value={kp}
                              index={conceptIndex}
                              onLaunch={launchConcept}
                              style={{ flex: 1, fontSize: size.bodySm, color: c.ink, lineHeight: size.bodySm * 1.5 }}
                            />
                          </View>
                        ))}
                      </View>
                    </>
                  )}

                  <View style={{ flexDirection: 'row', gap: 18, flexWrap: 'wrap', marginTop: space[6], marginBottom: 12 }}>
                    <TrustLink label="Says who?" color={c.confirm} onPress={() => setShowProvenance(true)} />
                    <TrustLink label="Read the original" color={c.confirm} onPress={() => router.push({ pathname: '/source', params: { topicId, courseId } })} />
                    <TrustLink label="Report" color={c.inkTertiary} onPress={() => setShowReport(true)} />
                  </View>
                  {builtBy ? (
                    <Text style={{ fontSize: size.bodySm, color: c.inkTertiary, paddingBottom: 8 }}>{builtBy}</Text>
                  ) : knowledge && knowledge.source_count > 0 ? (
                    <Text style={{ fontSize: size.bodySm, color: c.inkTertiary, paddingBottom: 8 }}>
                      Built from {knowledge.source_count} {knowledge.source_count === 1 ? 'source' : 'sources'}
                    </Text>
                  ) : null}

                  {topicId && <NoteStudyPrompt topicId={topicId} courseId={courseId} />}
                </>
              ) : null}
            </View>
          </>
        )}
      </ScrollView>

      {sheet && (
        <RetrievalSheet
          selection={sheet}
          onClose={() => setSheet(null)}
          onStart={startRetrieval}
          onExplainMyWay={explainConceptMyWay}
        />
      )}

      <Sheet open={showProvenance} onClose={() => setShowProvenance(false)} title="Says who?">
        <Text style={{ color: c.inkSecondary, fontSize: size.body, lineHeight: size.body * 1.5 }}>
          {knowledge && knowledge.source_count > 0
            ? `This note is synthesized from the ${knowledge.source_count} ${knowledge.source_count === 1 ? 'source' : 'sources'} uploaded to this topic — nothing invented. Open “Read the original” to see the exact material behind it.`
            : 'This note is synthesized only from material uploaded to this topic — nothing invented.'}
        </Text>
        {builtBy && (
          <Text style={{ marginTop: 12, fontFamily: font.utility, fontSize: size.utility, letterSpacing: trackingUtility(size.utility), textTransform: 'uppercase', color: c.inkTertiary }}>
            {builtBy}
          </Text>
        )}
        <Button
          label="Read the original"
          variant="secondary"
          onPress={() => {
            setShowProvenance(false);
            router.push({ pathname: '/source', params: { topicId, courseId } });
          }}
          style={{ width: '100%', marginTop: 16 }}
        />
      </Sheet>

      {showReport && <ReportSheet onClose={() => setShowReport(false)} />}

      {showTutor && (
        <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: c.paper, zIndex: 45 }}>
          <AITutorChat onBack={() => setShowTutor(false)} scope={title} />
        </View>
      )}
    </SafeAreaView>
  );
}

function RetrievalSheet({
  selection,
  onClose,
  onStart,
  onExplainMyWay,
}: {
  selection: SheetSelection;
  onClose: () => void;
  onStart: () => void;
  onExplainMyWay: (instruction: string) => void;
}) {
  const { c, font, size } = useTheme();
  const { concept, state } = selection;
  const label = stateLabel(state);
  const color = stateColor(c, state);
  const [asking, setAsking] = useState(false);
  const [instruction, setInstruction] = useState('');

  if (asking) {
    return (
      <Sheet open onClose={onClose} title={`Explain: ${concept}`}>
        <Textarea
          label="What do you want explained?"
          placeholder="e.g. focus on why this happens, not just what it is"
          value={instruction}
          onChangeText={setInstruction}
          rows={3}
        />
        <Button
          label="Generate audio"
          onPress={() => onExplainMyWay(instruction.trim())}
          disabled={!instruction.trim()}
          style={{ width: '100%', marginTop: 14 }}
        />
        <Button label="Back" variant="text" onPress={() => setAsking(false)} style={{ width: '100%', marginTop: 10 }} />
      </Sheet>
    );
  }

  return (
    <Sheet open onClose={onClose} title={`Retrieve: ${concept}`}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: color }} />
        <Text style={{ fontFamily: font.utility, fontSize: size.utility, textTransform: 'uppercase', color }}>
          {label} — worth a quick check
        </Text>
      </View>
      <Text style={{ marginBottom: 18, fontSize: size.body, color: c.ink }}>
        {`In your own words: what does ${concept} actually do, and how does it connect to the rest of the topic?`}
      </Text>
      <Button label="Start retrieval" onPress={onStart} style={{ width: '100%' }} />
      <Button label="Explain this my way" variant="secondary" onPress={() => setAsking(true)} style={{ width: '100%', marginTop: 10 }} />
      <Button label="Back to reading" variant="text" onPress={onClose} style={{ width: '100%', marginTop: 10 }} />
    </Sheet>
  );
}
