import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { IconButton } from '@/components/ui/IconButton';
import { PickedFile, uploadFilesToCloudinary } from '@/lib/cloudinary';
import { PermissionDeniedError, pickDocuments, pickPhotos, takePhoto } from '@/lib/filePicker';
import {
  CaptureEvent,
  CaptureFailedItem,
  CaptureTopicResult,
  isCaptureEvent,
  startCapture,
} from '@/lib/capture';
import { CourseSocket } from '@/lib/courseSocket';
import { OutlineScaffold } from '@/components/capture/OutlineScaffold';

// Capture is instant-and-dumb: pick files → upload to Cloudinary → POST the URLs → the
// server returns 202 and a worker transcribes, sorts into topics, and auto-files, telling
// us how it went over the course WebSocket. There is no "confirm structure" step — the
// worker files without asking — so the final screen is a result, not an approval gate.
//
// Capture has two intents that share this modal: the dump (below) and the syllabus
// scaffold (OutlineScaffold). `mode=outline` opens straight into the scaffold; otherwise
// the dump leads and offers a link across. Both are course-level surfaces of api/capture.py.
type Intent = 'dump' | 'outline';
type Phase = 'source' | 'uploading' | 'working' | 'done' | 'failed';
type WorkStage = 'transcribing' | 'organizing';

interface SourceOption {
  key: string;
  label: string;
  hint: string;
  pick: () => Promise<PickedFile[]>;
}

const STAGE_LABEL: Record<WorkStage, string> = {
  transcribing: 'Reading your material…',
  organizing: 'Sorting it into topics…',
};

function readError(err: unknown): string {
  if (err instanceof PermissionDeniedError) return err.message;
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') return err.response.data.detail;
  if (err instanceof Error) return err.message;
  return 'Something went wrong. Try again.';
}

export default function CaptureDump() {
  const { c, font, size, space } = useTheme();
  const { courseId, mode } = useLocalSearchParams<{ courseId?: string; mode?: string }>();

  const [intent, setIntent] = useState<Intent>(mode === 'outline' ? 'outline' : 'dump');
  const [phase, setPhase] = useState<Phase>('source');
  const [stage, setStage] = useState<WorkStage>('transcribing');
  const [topics, setTopics] = useState<CaptureTopicResult[]>([]);
  const [failed, setFailed] = useState<CaptureFailedItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<CourseSocket | null>(null);
  const batchIdRef = useRef<string | null>(null);

  // Tear the socket down if the user leaves mid-capture.
  useEffect(() => () => socketRef.current?.disconnect(), []);

  const handleEvent = (msg: { type?: string } & Record<string, unknown>) => {
    if (!isCaptureEvent(msg)) return;
    const event = msg as CaptureEvent;
    // Only react to our own batch (null ref = event beat the POST response; still ours).
    if (batchIdRef.current && event.batch_id !== batchIdRef.current) return;

    if (event.type === 'capture_progress') {
      setStage(event.stage);
    } else if (event.type === 'capture_complete') {
      setTopics(event.topics);
      setFailed(event.failed);
      setPhase('done');
      socketRef.current?.disconnect();
    } else if (event.type === 'capture_failed') {
      setFailed(event.failed);
      setError('Couldn’t read any of those files. Try clearer photos or another format.');
      setPhase('failed');
      socketRef.current?.disconnect();
    }
  };

  const runCapture = async (picker: () => Promise<PickedFile[]>) => {
    if (!courseId) {
      setError('No course selected.');
      setPhase('failed');
      return;
    }
    setError(null);

    let files: PickedFile[];
    try {
      files = await picker();
    } catch (err) {
      setError(readError(err));
      return; // stay on the source screen so they can retry / pick another source
    }
    if (files.length === 0) return; // cancelled picker

    setPhase('uploading');
    try {
      // Subscribe to the room before the work starts so no early event is missed.
      const socket = new CourseSocket(courseId, { onMessage: handleEvent });
      socketRef.current = socket;
      await socket.connect();

      const uploaded = await uploadFilesToCloudinary(files, `notesos/${courseId}/capture`);
      const accepted = await startCapture(courseId, uploaded);
      batchIdRef.current = accepted.batch_id;
      setStage('transcribing');
      setPhase('working');
    } catch (err) {
      socketRef.current?.disconnect();
      setError(readError(err));
      setPhase('failed');
    }
  };

  const reset = () => {
    socketRef.current?.disconnect();
    socketRef.current = null;
    batchIdRef.current = null;
    setTopics([]);
    setFailed([]);
    setError(null);
    setPhase('source');
  };

  const SOURCES: SourceOption[] = [
    { key: 'files', label: 'Upload files', hint: 'PDF, DOCX, images, audio — many at once', pick: pickDocuments },
    { key: 'photo', label: 'Snap photos', hint: 'Boards, slides, handwriting — snap as many as you like', pick: takePhoto },
    { key: 'library', label: 'Choose photos', hint: 'Pick several from your library', pick: pickPhotos },
  ];

  const titleStyle = { fontFamily: font.display, fontSize: size.display3, color: c.ink };
  const mutedBody = { color: c.inkSecondary, fontSize: size.bodySm, marginBottom: 8 };
  const rowStyle = {
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: c.paperEdge,
    minHeight: 44,
  } as const;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text style={titleStyle}>{intent === 'outline' ? 'Set up topics' : 'Add material'}</Text>
        <IconButton icon={<Text style={{ fontSize: 20, color: c.inkSecondary }}>✕</Text>} label="Close" onPress={() => router.back()} />
      </View>

      <ScrollView contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 20 }}>
        {intent === 'outline' ? (
          !courseId ? (
            <Text style={{ color: c.stateShaky, fontSize: size.bodySm, marginTop: 14 }}>No course selected.</Text>
          ) : (
            <View style={{ gap: 16 }}>
              <OutlineScaffold courseId={courseId} onDone={() => router.back()} />
              <Pressable onPress={() => setIntent('dump')} style={{ minHeight: 44, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ color: c.inkTertiary, fontSize: size.bodySm }}>Add material instead</Text>
              </Pressable>
            </View>
          )
        ) : (
        <>
        {phase === 'source' && (
          <View>
            <Text style={mutedBody}>Dump everything at once — no need to sort first.</Text>
            {SOURCES.map((source) => (
              <Pressable key={source.key} onPress={() => runCapture(source.pick)} style={rowStyle}>
                <Text style={{ fontFamily: font.bodySemibold, color: c.ink }}>{source.label}</Text>
                <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>{source.hint}</Text>
              </Pressable>
            ))}
            <Pressable onPress={() => setIntent('outline')} style={{ paddingTop: 16, minHeight: 44, justifyContent: 'center' }}>
              <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>
                Set up topics from a syllabus instead
              </Text>
            </Pressable>
            {error && <Text style={{ color: c.stateShaky, fontSize: size.bodySm, marginTop: 14 }}>{error}</Text>}
          </View>
        )}

        {phase === 'uploading' && (
          <View style={{ alignItems: 'center', gap: 14, paddingTop: 60 }}>
            <ActivityIndicator color={c.ink} />
            <Text style={{ color: c.inkSecondary, fontSize: size.body }}>Uploading your files…</Text>
          </View>
        )}

        {phase === 'working' && (
          <View style={{ alignItems: 'center', gap: 14, paddingTop: 60 }}>
            <ActivityIndicator color={c.ink} />
            <Text style={{ color: c.ink, fontSize: size.body }}>{STAGE_LABEL[stage]}</Text>
            <Text style={{ color: c.inkTertiary, fontSize: size.bodySm, textAlign: 'center' }}>
              You can leave this screen — it keeps going in the background.
            </Text>
          </View>
        )}

        {phase === 'done' && (
          <View>
            <Text style={[mutedBody, { marginTop: 6 }]}>Filed into your topics:</Text>
            {topics.map((topic) => {
              const review = topic.resources.filter((r) => r.needs_review).length;
              return (
                <View key={topic.topic_id} style={rowStyle}>
                  <Text style={{ fontFamily: font.bodySemibold, color: c.ink }}>{topic.title ?? 'Topic'}</Text>
                  <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>
                    {topic.resources.length} item{topic.resources.length === 1 ? '' : 's'}
                    {review > 0 ? ` · ${review} to check` : ''}
                  </Text>
                </View>
              );
            })}
            {failed.length > 0 && (
              <Text style={{ color: c.stateFading, fontSize: size.bodySm, marginTop: 12 }}>
                {failed.length} file{failed.length === 1 ? '' : 's'} couldn’t be read and {failed.length === 1 ? 'was' : 'were'} skipped.
              </Text>
            )}
            <Button label="Back to course" onPress={() => router.back()} style={{ marginTop: 18 }} />
            <Button label="Add more" variant="secondary" onPress={reset} style={{ marginTop: 10 }} />
          </View>
        )}

        {phase === 'failed' && (
          <View style={{ gap: 14, paddingTop: 40 }}>
            <Text style={[titleStyle, { textAlign: 'center' }]}>That didn’t work</Text>
            {error && <Text style={{ color: c.stateShaky, fontSize: size.bodySm, textAlign: 'center' }}>{error}</Text>}
            <Button label="Try again" onPress={reset} style={{ marginTop: 10 }} />
            <Button label="Close" variant="secondary" onPress={() => router.back()} />
          </View>
        )}
        </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
