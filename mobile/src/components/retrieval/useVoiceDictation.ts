import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from 'expo-speech-recognition';

// iOS caps a single SFSpeechRecognizer utterance at ~1 min, so a longer answer needs the
// recognizer restarted when the OS auto-ends it. We chunk-restart under the hood and hard-cap
// the whole spoken answer at 5 min — dictation is a short-answer tool, not lecture capture
// (that path is server Whisper). 5 min is a generous ceiling that also bounds battery drain.
const MAX_DICTATION_MS = 5 * 60 * 1000;
const START_OPTIONS = { lang: 'en-US', interimResults: true, continuous: true } as const;

// On-device speech-to-text for spoken answers. Transcription happens on the OS (offline,
// free, live partial results) and streams into the answer field — the editable field is the
// confirm step, so a mis-heard word is corrected before grading, same as the paper flow.
export function useVoiceDictation(value: string, onChangeText: (t: string) => void) {
  const [recognizing, setRecognizing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Handlers must read the latest text/callback, but the event listeners register once —
  // so route everything through refs (synced in an effect) to avoid stale closures.
  const baseRef = useRef('');
  const valueRef = useRef(value);
  const onTextRef = useRef(onChangeText);
  useEffect(() => {
    valueRef.current = value;
    onTextRef.current = onChangeText;
  });

  // activeRef = the user wants to keep dictating; distinguishes an OS auto-end mid-session
  // (restart) from a real stop (finish). deadlineRef bounds the whole session.
  const activeRef = useRef(false);
  const deadlineRef = useRef(0);
  const capTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearCapTimer = useCallback(() => {
    if (capTimerRef.current) {
      clearTimeout(capTimerRef.current);
      capTimerRef.current = null;
    }
  }, []);

  const finish = useCallback(() => {
    activeRef.current = false;
    clearCapTimer();
    setRecognizing(false);
  }, [clearCapTimer]);

  useSpeechRecognitionEvent('start', () => setRecognizing(true));
  useSpeechRecognitionEvent('end', () => {
    // OS ended a chunk. If the user still wants to talk and we're under the cap, keep the
    // accumulated text as the new base and restart; otherwise the session is genuinely done.
    if (activeRef.current && Date.now() < deadlineRef.current) {
      baseRef.current = valueRef.current.trim();
      ExpoSpeechRecognitionModule.start(START_OPTIONS);
      return;
    }
    finish();
  });
  useSpeechRecognitionEvent('result', (event) => {
    const transcript = event.results?.[0]?.transcript ?? '';
    if (!transcript) return;
    const base = baseRef.current;
    onTextRef.current(base ? `${base} ${transcript}` : transcript);
  });
  useSpeechRecognitionEvent('error', (event) => {
    setError(event.message || 'Didn’t catch that — try again.');
    finish();
  });

  // Never leave the recognizer or timer running if the field unmounts mid-session.
  useEffect(() => {
    return () => {
      activeRef.current = false;
      clearCapTimer();
      ExpoSpeechRecognitionModule.stop();
    };
  }, [clearCapTimer]);

  const stop = useCallback(() => {
    activeRef.current = false;
    clearCapTimer();
    ExpoSpeechRecognitionModule.stop();
  }, [clearCapTimer]);

  const toggle = useCallback(async () => {
    if (recognizing) {
      stop();
      return;
    }
    setError(null);
    const perm = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    if (!perm.granted) {
      setError('Microphone access is off — enable it in Settings to speak your answer.');
      return;
    }
    baseRef.current = valueRef.current.trim();  // keep anything already typed, append speech
    activeRef.current = true;
    deadlineRef.current = Date.now() + MAX_DICTATION_MS;
    clearCapTimer();
    capTimerRef.current = setTimeout(() => {
      setError('Reached the 5-minute limit — tap the mic to keep going.');
      stop();
    }, MAX_DICTATION_MS);
    ExpoSpeechRecognitionModule.start(START_OPTIONS);
  }, [recognizing, stop, clearCapTimer]);

  return { recognizing, error, toggle };
}
