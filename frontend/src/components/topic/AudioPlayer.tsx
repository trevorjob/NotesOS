'use client';

import { useEffect, useRef, useState } from 'react';
import { useKnowledgeStore } from '@/stores/knowledge';
import { Spinner } from '@/components/ui/Spinner';

const SPEEDS = [1, 1.25, 1.5, 2] as const;
type Speed = (typeof SPEEDS)[number];

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

interface AudioPlayerProps {
  topicId: string;
}

export function AudioPlayer({ topicId }: AudioPlayerProps) {
  const audio = useKnowledgeStore((s) => s.topicAudio[topicId]);
  const startPolling = useKnowledgeStore((s) => s.startPollingAudio);

  const ref = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0); // 0–100
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [speed, setSpeed] = useState<Speed>(1);
  const [visible, setVisible] = useState(true);

  // Poll while processing
  useEffect(() => {
    if (audio?.status === 'processing' || audio?.status === 'pending') {
      return startPolling(topicId);
    }
  }, [audio?.status, topicId, startPolling]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.playbackRate = speed;
  }, [speed]);

  function togglePlay() {
    const el = ref.current;
    if (!el) return;
    if (playing) { el.pause(); setPlaying(false); }
    else { el.play(); setPlaying(true); }
  }

  function rewind() {
    const el = ref.current;
    if (!el) return;
    el.currentTime = Math.max(0, el.currentTime - 10);
  }

  function onTimeUpdate() {
    const el = ref.current;
    if (!el) return;
    setCurrent(el.currentTime);
    setProgress(el.duration ? (el.currentTime / el.duration) * 100 : 0);
  }

  function onLoadedMetadata() {
    const el = ref.current;
    if (!el) return;
    setDuration(el.duration);
  }

  function onEnded() {
    setPlaying(false);
    setProgress(0);
    setCurrent(0);
  }

  function seek(e: React.MouseEvent<HTMLDivElement>) {
    const el = ref.current;
    if (!el || !el.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    el.currentTime = pct * el.duration;
  }

  if (!audio) return null;

  if ((audio.status === 'pending' || audio.status === 'processing') && !audio.audio_url) {
    return (
      <div className="bg-white rounded-2xl border border-[#dedad4] px-5 py-4 flex items-center gap-3">
        <Spinner size="sm" />
        <p className="text-sm text-[#6b6762]">Generating audio lesson…</p>
      </div>
    );
  }

  if (audio.status === 'failed' || !audio.audio_url) return null;

  if (!visible) {
    return (
      <button
        onClick={() => setVisible(true)}
        className="text-xs text-[#6b6762] hover:text-[#1a1917] transition-colors mb-2"
      >
        Show audio player
      </button>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-[#dedad4] px-5 py-4">
      {/* Hidden audio element */}
      <audio
        ref={ref}
        src={audio.audio_url}
        onTimeUpdate={onTimeUpdate}
        onLoadedMetadata={onLoadedMetadata}
        onEnded={onEnded}
        preload="metadata"
      />

      <div className="flex items-center gap-3">
        {/* Rewind 10s */}
        <button
          onClick={rewind}
          title="Rewind 10s"
          className="p-1.5 rounded-lg hover:bg-[#f0eeea] transition-colors text-[#6b6762]"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z" fill="currentColor"/>
            <text x="9" y="16" fontSize="6" fill="white" fontWeight="bold">10</text>
          </svg>
        </button>

        {/* Play/Pause */}
        <button
          onClick={togglePlay}
          className="w-10 h-10 rounded-full bg-[#1a1917] text-white flex items-center justify-center hover:opacity-90 transition-opacity shrink-0"
        >
          {playing ? (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="3" y="2" width="3.5" height="12" rx="1" fill="currentColor"/>
              <rect x="9.5" y="2" width="3.5" height="12" rx="1" fill="currentColor"/>
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M4 2l10 6-10 6V2z" fill="currentColor"/>
            </svg>
          )}
        </button>

        {/* Progress bar */}
        <div className="flex-1 flex items-center gap-2">
          <span className="text-xs text-[#9e9a94] w-9 text-right tabular-nums">{formatTime(current)}</span>
          <div
            className="flex-1 h-1.5 bg-[#e8e5e0] rounded-full cursor-pointer"
            onClick={seek}
          >
            <div
              className="h-1.5 bg-[#1a1917] rounded-full transition-all duration-100"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-xs text-[#9e9a94] w-9 tabular-nums">{formatTime(duration)}</span>
        </div>

        {/* Speed selector */}
        <button
          onClick={() => {
            const idx = SPEEDS.indexOf(speed);
            setSpeed(SPEEDS[(idx + 1) % SPEEDS.length]);
          }}
          className="text-xs font-medium text-[#6b6762] hover:text-[#1a1917] w-10 text-center transition-colors"
        >
          {speed}x
        </button>

        {/* Hide */}
        <button
          onClick={() => setVisible(false)}
          className="p-1.5 text-[#9e9a94] hover:text-[#6b6762] transition-colors"
          title="Hide player"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M10 3L4 11M4 3l6 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
      </div>
    </div>
  );
}
