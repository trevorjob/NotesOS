'use client';

import { useEffect, useRef, useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { Button } from '@/components/ui/Button';

type RecordState = 'idle' | 'recording' | 'recorded';

interface VoiceRecorderWidgetProps {
  onRecordingComplete?: (file: File) => void;
  onClear?: () => void;
  className?: string;
}

export function VoiceRecorderWidget({ onRecordingComplete, onClear, className = '' }: VoiceRecorderWidgetProps) {
  const [state, setState] = useState<RecordState>('idle');
  const [seconds, setSeconds] = useState(0);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pad = (n: number) => String(n).padStart(2, '0');

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        const url = URL.createObjectURL(blob);
        setBlobUrl(url);
        const file = new File([blob], 'voice.webm', { type: 'audio/webm' });
        onRecordingComplete?.(file);
        stream.getTracks().forEach((t) => t.stop());
      };
      recorder.start();
      mediaRef.current = recorder;
      setState('recording');
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch (err) {
      console.error('Microphone access denied', err);
    }
  };

  const stop = () => {
    mediaRef.current?.stop();
    if (timerRef.current) clearInterval(timerRef.current);
    setState('recorded');
  };

  const clear = () => {
    if (blobUrl) URL.revokeObjectURL(blobUrl);
    setBlobUrl(null);
    setState('idle');
    setSeconds(0);
    onClear?.();
  };

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

  return (
    <div className={`flex flex-col gap-3 ${className}`}>
      {state === 'idle' && (
        <Button
          variant="secondary"
          size="md"
          onClick={start}
          iconLeft="mic"
          className="self-start"
        >
          Record voice answer
        </Button>
      )}

      {state === 'recording' && (
        <div className="flex items-center gap-3">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--color-error)] opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-[var(--color-error)]" />
          </span>
          <span className="text-sm font-mono text-[var(--color-error)] font-semibold">
            REC {pad(Math.floor(seconds / 60))}:{pad(seconds % 60)}
          </span>
          <Button variant="danger" size="sm" onClick={stop} iconLeft="stop">
            Stop
          </Button>
        </div>
      )}

      {state === 'recorded' && blobUrl && (
        <div className="flex items-center gap-3 flex-wrap">
          <audio controls src={blobUrl} className="h-9" />
          <Button variant="ghost" size="sm" onClick={clear} iconLeft="delete">
            Discard
          </Button>
        </div>
      )}
    </div>
  );
}
