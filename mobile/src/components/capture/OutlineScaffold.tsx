import React, { useState } from 'react';
import { ActivityIndicator, Text, TextInput, View } from 'react-native';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { PickedFile, uploadFilesToCloudinary } from '@/lib/cloudinary';
import { PermissionDeniedError, pickPhotos, takePhoto } from '@/lib/filePicker';
import { OutlineResult, scaffoldOutline } from '@/lib/capture';

// Set a course's topic skeleton up front from its syllabus. Reused by the capture modal
// (as the "set up topics" intent) and the topics empty-state. Synchronous — paste text
// and/or snap photos (uploaded to Cloudinary, transcribed server-side) → the server parses
// them into empty labeled topics. Seeding topics this way is what lets a later dump
// classify files into the right buckets instead of guessing clusters.
type Phase = 'form' | 'submitting' | 'done';

interface OutlineScaffoldProps {
  courseId: string;
  onDone: () => void;
}

function readError(err: unknown): string {
  if (err instanceof PermissionDeniedError) return err.message;
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') return err.response.data.detail;
  if (err instanceof Error) return err.message;
  return 'Something went wrong. Try again.';
}

export function OutlineScaffold({ courseId, onDone }: OutlineScaffoldProps) {
  const { c, font, size, radius, lineHeight } = useTheme();

  const [text, setText] = useState('');
  const [photos, setPhotos] = useState<PickedFile[]>([]);
  const [phase, setPhase] = useState<Phase>('form');
  const [result, setResult] = useState<OutlineResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = text.trim().length > 0 || photos.length > 0;

  const addPhotos = async (picker: () => Promise<PickedFile[]>) => {
    setError(null);
    try {
      const picked = await picker();
      if (picked.length) setPhotos((prev) => [...prev, ...picked]);
    } catch (err) {
      setError(readError(err));
    }
  };

  const submit = async () => {
    if (!canSubmit) return;
    setError(null);
    setPhase('submitting');
    try {
      let imageUrls: string[] = [];
      if (photos.length) {
        const uploaded = await uploadFilesToCloudinary(photos, `notesos/${courseId}/outline`);
        imageUrls = uploaded.map((u) => u.url);
      }
      const res = await scaffoldOutline(courseId, { text: text.trim() || undefined, imageUrls });
      setResult(res);
      setPhase('done');
    } catch (err) {
      setError(readError(err));
      setPhase('form');
    }
  };

  const titleStyle = { fontFamily: font.display, fontSize: size.display3, color: c.ink };

  if (phase === 'submitting') {
    return (
      <View style={{ alignItems: 'center', gap: 14, paddingTop: 60 }}>
        <ActivityIndicator color={c.ink} />
        <Text style={{ color: c.inkSecondary, fontSize: size.body }}>Reading your syllabus…</Text>
      </View>
    );
  }

  if (phase === 'done' && result) {
    return (
      <View style={{ gap: 12 }}>
        <Text style={titleStyle}>{result.created.length ? 'Topics set up' : 'All set'}</Text>
        {result.created.length === 0 ? (
          <Text style={{ color: c.inkSecondary, fontSize: size.body }}>
            No new topics — they may already be here.
          </Text>
        ) : (
          result.created.map((topic) => (
            <View key={topic.id} style={{ paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: c.paperEdge }}>
              <Text style={{ fontFamily: font.bodySemibold, color: c.ink }}>{topic.title}</Text>
              {topic.week_number != null && (
                <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>Week {topic.week_number}</Text>
              )}
            </View>
          ))
        )}
        {result.skipped.length > 0 && (
          <Text style={{ color: c.inkTertiary, fontSize: size.bodySm }}>
            {result.skipped.length} already existed and {result.skipped.length === 1 ? 'was' : 'were'} kept as-is.
          </Text>
        )}
        <Button label="Done" onPress={onDone} style={{ marginTop: 8 }} />
      </View>
    );
  }

  return (
    <View style={{ gap: 14 }}>
      <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>
        Paste your syllabus or snap a photo of it — we’ll set up your topics so everything you
        add later lands in the right place.
      </Text>

      <TextInput
        value={text}
        onChangeText={setText}
        placeholder="Paste your course outline / syllabus here…"
        placeholderTextColor={c.inkTertiary}
        multiline
        textAlignVertical="top"
        style={{
          minHeight: 140,
          borderWidth: 1,
          borderColor: c.paperEdge,
          borderRadius: radius.sm,
          padding: 14,
          fontFamily: font.body,
          fontSize: size.body,
          color: c.ink,
          backgroundColor: c.paper,
          lineHeight: size.body * lineHeight.body,
        }}
      />

      <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
        <Button label="Snap syllabus" variant="secondary" size="sm" onPress={() => addPhotos(takePhoto)} />
        <Button label="Choose photos" variant="secondary" size="sm" onPress={() => addPhotos(pickPhotos)} />
      </View>
      {photos.length > 0 && (
        <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>
          {photos.length} syllabus photo{photos.length === 1 ? '' : 's'} added
        </Text>
      )}

      {error && <Text style={{ color: c.stateShaky, fontSize: size.bodySm }}>{error}</Text>}

      <Button label="Set up my topics" onPress={submit} disabled={!canSubmit} />
    </View>
  );
}
