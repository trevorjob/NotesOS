import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';
import { File } from 'expo-file-system';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { PickedFile } from '@/lib/cloudinary';

// In-app lecture recorder. Records fully on-device (no network needed), then hands the
// finished file to the parent, which runs it through the same Cloudinary→/capture path a
// picked audio file uses. Recording is a native module — the app must be rebuilt with a
// dev client (npx expo prebuild) before this screen works on device.

type Status = 'checking' | 'denied' | 'ready';

// Below this we assume the tap was a mis-fire, not a real recording.
const MIN_DURATION_MS = 700;
// Safety net so a forgotten recording can't grow unbounded (2 hours).
const MAX_DURATION_MS = 2 * 60 * 60 * 1000;

interface AudioRecorderProps {
  onComplete: (file: PickedFile) => void;
  onCancel: () => void;
}

function formatDuration(ms: number): string {
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, '0');
  const ss = String(s).padStart(2, '0');
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function AudioRecorder({ onComplete, onCancel }: AudioRecorderProps) {
  const { c, font, size } = useTheme();
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const state = useAudioRecorderState(recorder);

  const [status, setStatus] = useState<Status>('checking');
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const stoppingRef = useRef(false);
  const maxTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const permission = await AudioModule.requestRecordingPermissionsAsync();
        if (!active) return;
        if (!permission.granted) {
          setStatus('denied');
          return;
        }
        await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
        if (active) setStatus('ready');
      } catch {
        if (active) setError('Couldn’t start the microphone. Try again.');
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const stopRecording = useCallback(async () => {
    if (stoppingRef.current) return; // guard the manual-stop / auto-stop race
    stoppingRef.current = true;
    if (maxTimerRef.current) clearTimeout(maxTimerRef.current);
    setProcessing(true);
    try {
      await recorder.stop();
      const uri = recorder.uri;
      const file = uri ? new File(uri) : null;
      if (!file || !file.exists || file.size <= 0) {
        setError('That recording didn’t save. Give it another go.');
        return;
      }
      if (state.durationMillis < MIN_DURATION_MS) {
        file.delete();
        setError('That was too short to save. Hold on a little longer.');
        return;
      }
      onComplete({ uri: file.uri, name: `lecture-${Date.now()}.m4a`, mimeType: 'audio/m4a' });
    } catch {
      setError('Something went wrong saving that recording. Try again.');
    } finally {
      setProcessing(false);
      stoppingRef.current = false;
    }
  }, [recorder, state.durationMillis, onComplete]);

  const startRecording = async () => {
    setError(null);
    try {
      await recorder.prepareToRecordAsync();
      recorder.record();
      // Native safety net so a forgotten recording can't grow unbounded.
      maxTimerRef.current = setTimeout(() => void stopRecording(), MAX_DURATION_MS);
    } catch {
      setError('Couldn’t start recording. Try again.');
    }
  };

  // Clear the safety timer if the screen unmounts mid-recording.
  useEffect(() => () => {
    if (maxTimerRef.current) clearTimeout(maxTimerRef.current);
  }, []);

  const titleStyle = { fontFamily: font.display, fontSize: size.display3, color: c.ink };

  if (status === 'checking') {
    return (
      <View style={{ alignItems: 'center', gap: 14, paddingTop: 60 }}>
        <ActivityIndicator color={c.ink} />
        <Text style={{ color: c.inkSecondary, fontSize: size.body }}>Getting the mic ready…</Text>
      </View>
    );
  }

  if (status === 'denied') {
    return (
      <View style={{ gap: 14, paddingTop: 40 }}>
        <Text style={[titleStyle, { textAlign: 'center' }]}>Mic is off</Text>
        <Text style={{ color: c.inkSecondary, fontSize: size.bodySm, textAlign: 'center' }}>
          Turn on microphone access in Settings to record a lecture.
        </Text>
        <Button label="Back" variant="secondary" onPress={onCancel} style={{ marginTop: 10 }} />
      </View>
    );
  }

  const isRecording = state.isRecording;

  return (
    <View style={{ alignItems: 'center', gap: 20, paddingTop: 40 }}>
      <Text style={titleStyle}>{isRecording ? 'Recording…' : 'Record a lecture'}</Text>

      <Text style={{ fontFamily: font.body, fontSize: 44, color: isRecording ? c.stateShaky : c.inkTertiary }}>
        {formatDuration(state.durationMillis)}
      </Text>

      {!isRecording && !processing && (
        <Text style={{ color: c.inkSecondary, fontSize: size.bodySm, textAlign: 'center' }}>
          Tap to start. You can keep recording even with no signal — we’ll upload it once you’re back online.
        </Text>
      )}

      {processing ? (
        <View style={{ alignItems: 'center', gap: 10, paddingTop: 10 }}>
          <ActivityIndicator color={c.ink} />
          <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>Saving your recording…</Text>
        </View>
      ) : (
        <Pressable
          onPress={isRecording ? stopRecording : startRecording}
          accessibilityLabel={isRecording ? 'Stop recording' : 'Start recording'}
          style={{
            width: 88,
            height: 88,
            borderRadius: 44,
            backgroundColor: isRecording ? c.stateShaky : c.paper,
            borderWidth: 2,
            borderColor: c.stateShaky,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <View
            style={{
              width: isRecording ? 26 : 40,
              height: isRecording ? 26 : 40,
              borderRadius: isRecording ? 4 : 20,
              backgroundColor: isRecording ? c.paper : c.stateShaky,
            }}
          />
        </Pressable>
      )}

      {error && <Text style={{ color: c.stateShaky, fontSize: size.bodySm, textAlign: 'center' }}>{error}</Text>}

      {!isRecording && !processing && (
        <Button label="Back" variant="text" onPress={onCancel} style={{ marginTop: 4 }} />
      )}
    </View>
  );
}
