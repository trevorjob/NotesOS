import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from 'expo-speech-recognition';

const START_OPTIONS = { lang: 'en-US', interimResults: true, continuous: true } as const;
// One conversational turn is short; a guard keeps a stuck recognizer from running forever.
const MAX_TURN_MS = 2 * 60 * 1000;

// Push-to-talk speech input for a single conversational turn (conversational-modes §9). Live
// words stream into `partial` while recording; when the user stops (tap again, or the OS ends
// the utterance) the accumulated text is sent via onFinal — auto-advance, no confirm. iOS caps
// one utterance at ~1 min, so a longer turn chunk-restarts under the hood, same as dictation.
export function usePushToTalk(onFinal: (text: string) => void) {
  const [recording, setRecording] = useState(false);
  const [partial, setPartial] = useState('');
  const [error, setError] = useState<string | null>(null);

  const onFinalRef = useRef(onFinal);
  useEffect(() => {
    onFinalRef.current = onFinal;
  });

  // baseRef survives an OS chunk-restart within one turn; partialRef is the latest full text;
  // activeRef distinguishes a mid-turn auto-end (restart) from the user actually stopping.
  const baseRef = useRef('');
  const partialRef = useRef('');
  const activeRef = useRef(false);
  const deadlineRef = useRef(0);
  const capRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearCap = useCallback(() => {
    if (capRef.current) {
      clearTimeout(capRef.current);
      capRef.current = null;
    }
  }, []);

  const finalize = useCallback(() => {
    activeRef.current = false;
    clearCap();
    setRecording(false);
    const text = partialRef.current.trim();
    baseRef.current = '';
    partialRef.current = '';
    setPartial('');
    if (text) onFinalRef.current(text);
  }, [clearCap]);

  useSpeechRecognitionEvent('start', () => setRecording(true));
  useSpeechRecognitionEvent('result', (event) => {
    const transcript = event.results?.[0]?.transcript ?? '';
    const base = baseRef.current;
    const full = base ? `${base} ${transcript}` : transcript;
    partialRef.current = full;
    setPartial(full);
  });
  useSpeechRecognitionEvent('end', () => {
    // Still holding + under the guard → the OS ended a chunk, keep going (iOS ~1-min cap).
    // Otherwise the user (or the guard) stopped: finalize the turn and send it.
    if (activeRef.current && Date.now() < deadlineRef.current) {
      baseRef.current = partialRef.current.trim();
      ExpoSpeechRecognitionModule.start(START_OPTIONS);
      return;
    }
    finalize();
  });
  useSpeechRecognitionEvent('error', (event) => {
    setError(event.message || 'Didn’t catch that — try again.');
    activeRef.current = false;
    clearCap();
    setRecording(false);
  });

  useEffect(
    () => () => {
      activeRef.current = false;
      clearCap();
      ExpoSpeechRecognitionModule.stop();
    },
    [clearCap],
  );

  const stop = useCallback(() => {
    // Mark inactive so the pending 'end' finalizes-and-sends instead of chunk-restarting.
    activeRef.current = false;
    clearCap();
    ExpoSpeechRecognitionModule.stop();
  }, [clearCap]);

  const start = useCallback(async () => {
    setError(null);
    const perm = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    if (!perm.granted) {
      setError('Microphone access is off — enable it in Settings to speak.');
      return;
    }
    baseRef.current = '';
    partialRef.current = '';
    setPartial('');
    activeRef.current = true;
    deadlineRef.current = Date.now() + MAX_TURN_MS;
    clearCap();
    capRef.current = setTimeout(stop, MAX_TURN_MS);
    ExpoSpeechRecognitionModule.start(START_OPTIONS);
  }, [clearCap, stop]);

  return { recording, partial, error, start, stop };
}
