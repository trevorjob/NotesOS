'use client';

import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { Badge } from '@/components/ui/Badge';

interface Question {
  id: string;
  question_text: string;
  question_type: string;
  answer_options?: string[] | null;
  options?: string[] | null;
}

interface QuizQuestionProps {
  question: Question;
  index: number;
  total: number;
  onSubmit: (questionId: string, answer: string, isVoice?: boolean, voiceFile?: File) => void;
  onSkip: () => void;
  onPrevious?: () => void;
  defaultAnswer?: string;
  defaultIsVoice?: boolean;
  loading?: boolean;
}

const MCQ_TYPES = ['mcq', 'multiple_choice', 'multiple-choice'];

export function QuizQuestion({ question, index, total, onSubmit, onSkip, onPrevious, defaultAnswer, defaultIsVoice, loading }: QuizQuestionProps) {
  const normalizedType = question.question_type?.toLowerCase() ?? '';
  const options = question.answer_options ?? question.options ?? [];
  const isMCQ = MCQ_TYPES.includes(normalizedType) && options.length > 0;

  // If previously answered by voice, don't pre-fill textarea with '[voice answer]'
  const [answer, setAnswer] = useState(isMCQ ? '' : (defaultIsVoice ? '' : (defaultAnswer ?? '')));
  const [selectedOption, setSelectedOption] = useState(isMCQ ? (defaultAnswer ?? '') : '');
  const [recording, setRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    setAnswer(isMCQ ? '' : (defaultIsVoice ? '' : (defaultAnswer ?? '')));
    setSelectedOption(isMCQ ? (defaultAnswer ?? '') : '');
    setAudioBlob(null);
    if (recording) {
      mediaRecorderRef.current?.stop();
      setRecording(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question.id]);

  const progress = Math.round((index / total) * 100);

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => chunksRef.current.push(e.data);
      mr.onstop = () => {
        setAudioBlob(new Blob(chunksRef.current, { type: 'audio/webm' }));
        stream.getTracks().forEach((t) => t.stop());
      };
      mediaRecorderRef.current = mr;
      mr.start();
      setRecording(true);
    } catch {
      // Microphone unavailable
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  function handleSubmit() {
    if (isMCQ) {
      if (!selectedOption) return;
      onSubmit(question.id, selectedOption);
    } else if (audioBlob) {
      const file = new File([audioBlob], 'voice.webm', { type: 'audio/webm' });
      onSubmit(question.id, '[voice answer]', true, file);
    } else if (defaultIsVoice && !answer.trim()) {
      // Keep existing voice answer — signal with is_voice=true but no new file
      onSubmit(question.id, '[voice answer]', true);
    } else {
      if (!answer.trim()) return;
      onSubmit(question.id, answer.trim());
    }
  }

  const canSubmit = isMCQ ? !!selectedOption : (!!answer.trim() || !!audioBlob || !!defaultIsVoice);

  return (
    <div className="space-y-5">
      {/* Progress */}
      <div className="flex items-center gap-3">
        <ProgressBar value={progress} size="sm" className="flex-1" />
        <span className="text-xs text-[#9e9a94] shrink-0">{index + 1} / {total}</span>
      </div>

      {/* Type badge */}
      <Badge variant="muted">
        {isMCQ ? 'Multiple Choice' : normalizedType.replace(/_/g, ' ')}
      </Badge>

      {/* Question text */}
      <p className="text-base font-medium text-[#1a1917] leading-relaxed">{question.question_text}</p>

      {/* MCQ options — no text/voice input */}
      {isMCQ && (
        <div className="space-y-2">
          {options.map((opt) => (
            <button
              key={opt}
              onClick={() => setSelectedOption(opt)}
              className={`w-full text-left px-4 py-3 rounded-xl border text-sm transition-colors ${
                selectedOption === opt
                  ? 'border-[#1a1917] bg-[#1a1917] text-white'
                  : 'border-[#dedad4] text-[#1a1917] hover:border-[#9e9a94]'
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      )}

      {/* Free-text / voice — non-MCQ only */}
      {!isMCQ && (
        <div className="space-y-3">
          {/* Previously recorded voice answer indicator (shown when navigating back) */}
          {defaultIsVoice && !audioBlob && (
            <div className="flex items-center gap-2 px-3 py-2 bg-[#f0fdf4] border border-[#86efac] rounded-lg">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-[#16a34a] shrink-0">
                <rect x="9" y="2" width="6" height="12" rx="3" fill="currentColor"/>
                <path d="M5 10v2a7 7 0 0014 0v-2" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <line x1="12" y1="19" x2="12" y2="22" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
              <span className="text-xs text-[#16a34a] font-medium">Voice answer already recorded</span>
              <span className="text-xs text-[#6b6762] ml-1">— record again or type to replace</span>
            </div>
          )}
          <textarea
            value={answer}
            onChange={(e) => { setAnswer(e.target.value); setAudioBlob(null); }}
            placeholder={audioBlob ? 'Voice answer recorded — or type to override' : 'Type your answer…'}
            rows={4}
            disabled={!!audioBlob}
            className="w-full resize-y bg-[#f0eeea] border border-[#dedad4] rounded-xl px-4 py-3 text-sm text-[#1a1917] placeholder-[#9e9a94] focus:outline-none focus:border-[#1a1917] disabled:opacity-60"
          />

          {/* Voice recording controls */}
          <div className="flex items-center gap-3">
            {!recording && !audioBlob && (
              <button
                onClick={startRecording}
                className="flex items-center gap-1.5 text-xs text-[#6b6762] hover:text-[#1a1917] transition-colors"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <rect x="9" y="2" width="6" height="12" rx="3" fill="currentColor"/>
                  <path d="M5 10v2a7 7 0 0014 0v-2" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  <line x1="12" y1="19" x2="12" y2="22" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                Use voice instead
              </button>
            )}
            {recording && (
              <button
                onClick={stopRecording}
                className="flex items-center gap-1.5 text-xs text-[#dc2626] animate-pulse"
              >
                <span className="h-2 w-2 rounded-full bg-[#dc2626]" />
                Recording… tap to stop
              </button>
            )}
            {audioBlob && !recording && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-[#16a34a]">✓ Voice answer ready</span>
                <button
                  onClick={() => setAudioBlob(null)}
                  className="text-xs text-[#9e9a94] hover:text-[#dc2626] transition-colors"
                >
                  Remove
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-between items-center pt-2">
        <div className="flex items-center gap-2">
          {onPrevious && index > 0 && (
            <Button variant="ghost" size="sm" onClick={onPrevious}>
              ← Previous
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={onSkip}>
            {index + 1 === total ? 'Skip & finish' : 'Skip'}
          </Button>
        </div>
        <Button size="sm" loading={loading} onClick={handleSubmit} disabled={!canSubmit}>
          {index + 1 === total ? 'Submit quiz' : 'Next →'}
        </Button>
      </div>
    </div>
  );
}
