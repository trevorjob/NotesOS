'use client';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

interface QuestionResult {
  question_id: string;
  question_text: string;
  user_answer: string;
  score: number; // 0–1 (normalized from backend 0–10)
  feedback?: string;
  encouragement?: string;
  key_points_missed?: string[];
}

interface QuizResultsProps {
  score: number; // 0–100 percentage
  questionResults: QuestionResult[];
  onBack: () => void;
  onRetry?: () => void;
}

function ScoreRing({ score }: { score: number }) {
  const r = 40;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;

  return (
    <div className="relative h-28 w-28 shrink-0">
      <svg width="112" height="112" viewBox="0 0 112 112" className="-rotate-90">
        <circle cx="56" cy="56" r={r} fill="none" stroke="#e8e5e0" strokeWidth="10" />
        <circle
          cx="56" cy="56" r={r} fill="none"
          stroke={score >= 70 ? '#16a34a' : score >= 50 ? '#d97706' : '#dc2626'}
          strokeWidth="10"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-[#1a1917]">{Math.round(score)}%</span>
      </div>
    </div>
  );
}

function overallEncouragement(score: number): string {
  if (score >= 90) return 'Outstanding! You nailed it.';
  if (score >= 70) return 'Great work! Keep it up.';
  if (score >= 50) return "Good effort — review the missed concepts.";
  return "Keep studying — you'll get there!";
}

function resultBadge(s: number) {
  if (s >= 0.85) return <Badge variant="success">✓ Correct</Badge>;
  if (s >= 0.5) return <Badge variant="warning">~ Partial</Badge>;
  return <Badge variant="error">✗ Missed</Badge>;
}

export function QuizResults({
  score,
  questionResults,
  onBack,
  onRetry,
}: QuizResultsProps) {
  const correct = questionResults.filter((q) => q.score >= 0.85).length;
  const total = questionResults.length;

  // Collect all missed concepts across answers
  const allMissed = questionResults.flatMap((q) => q.key_points_missed ?? []);

  return (
    <div className="space-y-6">
      {/* Score */}
      <div className="flex items-center gap-6">
        <ScoreRing score={score} />
        <div>
          <p className="text-lg font-semibold text-[#1a1917]">{correct} / {total} correct</p>
          <p className="text-sm text-[#6b6762] mt-0.5">{overallEncouragement(score)}</p>
        </div>
      </div>

      {/* Missing concepts */}
      {allMissed.length > 0 && (
        <div className="bg-[#fffbeb] border border-[#fde68a] rounded-xl p-4">
          <p className="text-sm font-medium text-[#b45309] mb-2">Concepts to review</p>
          <ul className="space-y-1">
            {allMissed.map((c, i) => (
              <li key={i} className="text-sm text-[#b45309] flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#d97706] shrink-0" />
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Per-question breakdown */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-[#6b6762] uppercase tracking-wide">Breakdown</h3>
        {questionResults.map((r, i) => (
          <div key={r.question_id} className="bg-white border border-[#dedad4] rounded-xl p-4 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-medium text-[#1a1917] flex-1">
                {i + 1}. {r.question_text}
              </p>
              {resultBadge(r.score)}
            </div>
            <p className="text-xs text-[#6b6762]">Your answer: {r.user_answer || '(skipped)'}</p>
            {r.feedback && <p className="text-xs text-[#9e9a94] italic">{r.feedback}</p>}
            {r.encouragement && (
              <p className="text-xs text-[#16a34a]">{r.encouragement}</p>
            )}
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <Button variant="ghost" onClick={onBack}>Back to topic</Button>
        {onRetry && <Button onClick={onRetry}>Retry</Button>}
      </div>
    </div>
  );
}
