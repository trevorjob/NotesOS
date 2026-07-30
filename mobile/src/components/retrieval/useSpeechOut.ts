import { useCallback, useEffect, useRef, useState } from 'react';
import { AudioPlayer, createAudioPlayer, setAudioModeAsync } from 'expo-audio';
import { API_BASE_URL } from '@/lib/api';
import { getAccessToken } from '@/lib/auth';

const MAX_TTS_CHARS = 400;

// Voice-out for the AI's short conversational probes (conversational-modes §9). Uses the
// SERVER TTS provider (GET /api/retrieval/tts → OpenAI-TTS mp3) played through expo-audio —
// the "proper" voice, not on-device. A courtesy layer: any failure is swallowed so the loop
// stays text-first, and a mute toggle silences it.
export function useSpeechOut() {
  const [muted, setMuted] = useState(false);
  const mutedRef = useRef(muted);
  useEffect(() => {
    mutedRef.current = muted;
  }, [muted]);

  const playerRef = useRef<AudioPlayer | null>(null);
  const configuredRef = useRef(false);

  const release = useCallback(() => {
    try {
      playerRef.current?.remove();
    } catch {
      // already gone
    }
    playerRef.current = null;
  }, []);

  const speak = useCallback(
    async (text: string) => {
      const clean = text.trim();
      if (mutedRef.current || !clean) return;
      try {
        const token = await getAccessToken();
        if (!configuredRef.current) {
          await setAudioModeAsync({ playsInSilentMode: true });
          configuredRef.current = true;
        }
        release();
        const player = createAudioPlayer({
          uri: `${API_BASE_URL}/api/retrieval/tts?text=${encodeURIComponent(clean.slice(0, MAX_TTS_CHARS))}`,
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        });
        playerRef.current = player;
        player.play();
      } catch {
        // Courtesy layer — a TTS failure never blocks the text-first loop.
      }
    },
    [release],
  );

  const stop = useCallback(() => release(), [release]);
  const toggleMuted = useCallback(() => {
    setMuted((m) => {
      if (!m) release();
      return !m;
    });
  }, [release]);

  useEffect(() => () => release(), [release]);

  return { speak, stop, muted, toggleMuted };
}
