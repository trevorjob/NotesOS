import React from 'react';
import { Text, TextStyle, View } from 'react-native';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { MathText } from '@/components/retrieval/MathText';
import { AttemptResult, CalibrationLabel } from '@/lib/retrieval';

// Presentational pieces shared by the one-shot retrieval screen and the conversational bout
// (teach / ramble). Kept here so both render an identical result card + confidence vocabulary.

export type Theme = ReturnType<typeof useTheme>;

export interface ConfLevel {
  v: number;
  label: string;
}

export const CONF_LEVELS: ConfLevel[] = [
  { v: 0.25, label: 'Guessing' },
  { v: 0.6, label: 'Fairly sure' },
  { v: 0.9, label: 'Certain' },
];

export const CAL_COPY: Record<CalibrationLabel, string> = {
  calibrated: 'Calibrated — your confidence matched how it went.',
  underconfident: 'You knew more than you thought — nice.',
  overconfident: 'Overconfident here — worth another look, gently.',
};

export function readError(err: unknown): string {
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') return err.response.data.detail;
  if (err instanceof Error) return err.message;
  return 'Something went wrong. Try again.';
}

export function relativeDue(iso: string | null): string {
  if (!iso) return 'soon';
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return 'now';
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `in ${mins} min`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `in ${hrs} h`;
  const days = Math.round(hrs / 24);
  return `in ${days} day${days === 1 ? '' : 's'}`;
}

export function labelStyle(theme: Theme, color?: string): TextStyle {
  return {
    fontFamily: theme.font.utility,
    fontSize: theme.size.utility,
    letterSpacing: theme.trackingUtility(theme.size.utility),
    textTransform: 'uppercase',
    color: color ?? theme.c.inkTertiary,
  };
}

export function gradeColor(theme: Theme, grade: string): string {
  if (grade === 'good' || grade === 'easy') return theme.c.stateSolid;
  if (grade === 'hard') return theme.c.stateFading;
  return theme.c.stateShaky;
}

const SELF_GRADE_HEADLINE: Record<string, string> = {
  again: 'Worth another pass.',
  hard: 'Right method — a slip to tighten.',
  good: 'Solved it.',
  easy: 'Solved it cold.',
};

interface SingleResultProps {
  attempt: AttemptResult;
  objective: boolean;
  concept: string;
  onDone: () => void;
  onKeepGoing?: () => void;
  onFinish?: () => void;
}

// The single-concept outcome card (posed / open / conversational). Subjective modes show a
// score /10; objective modes show correct/not; a worked self-grade shows its own headline.
export function SingleResult({ attempt, objective, concept, onDone, onKeepGoing, onFinish }: SingleResultProps) {
  const theme = useTheme();
  const { c } = theme;
  const { outcome, state, calibration } = attempt;
  const isRight = outcome.score >= 1;
  const selfGraded = outcome.detail?.self_graded === true;
  const missed = Array.isArray(outcome.detail?.key_points_missed) ? (outcome.detail.key_points_missed as string[]) : [];

  const headline = selfGraded
    ? SELF_GRADE_HEADLINE[outcome.grade] ?? 'Marked.'
    : objective
      ? isRight
        ? 'Correct.'
        : 'Not quite.'
      : `${Math.round(outcome.score * 10)} / 10`;

  return (
    <View style={{ gap: 14 }}>
      <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display3, color: c.ink }}>{headline}</Text>
      {outcome.feedback && <MathText content={outcome.feedback} textStyle={{ fontSize: theme.size.body, color: c.inkSecondary }} />}

      {missed.length > 0 && (
        <View>
          <Text style={labelStyle(theme, c.stateShaky)}>Still fuzzy on</Text>
          {missed.map((item, i) => (
            <Text key={i} style={{ fontSize: theme.size.bodySm, color: c.inkSecondary, marginTop: 6 }}>{`• ${item}`}</Text>
          ))}
        </View>
      )}

      {calibration.predicted != null && calibration.label && <Text style={labelStyle(theme, gradeColor(theme, outcome.grade))}>{CAL_COPY[calibration.label]}</Text>}

      <Text style={{ fontSize: theme.size.bodySm, color: c.inkTertiary }}>{`${concept} — next review ${relativeDue(state.due)}`}</Text>

      {onKeepGoing && <Button label="Keep going" onPress={onKeepGoing} />}
      {onFinish ? (
        <Button label="Done for now" variant="text" onPress={onFinish} />
      ) : (
        <Button label="Back to reading" variant={onKeepGoing ? 'text' : undefined} onPress={onDone} />
      )}
    </View>
  );
}
