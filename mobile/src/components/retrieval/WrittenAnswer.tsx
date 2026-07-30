import React from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { useVoiceDictation } from '@/components/retrieval/useVoiceDictation';

interface Props {
  value: string;
  onChangeText: (t: string) => void;
  onSubmit: () => void;
  onSnapPaper: () => void;
  transcribing: boolean;
  paperHint: string | null;   // confirm-hint after a transcription, or a friendly read error
  rows?: number;
  submitLabel?: string;
  placeholder?: string;
}

interface AssistButtonProps {
  label: string;
  onPress: () => void;
  active?: boolean;
  disabled?: boolean;
  busy?: boolean;
}

function AssistButton({ label, onPress, active, disabled, busy }: AssistButtonProps) {
  const theme = useTheme();
  const { c } = theme;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={{
        flex: 1,
        minHeight: 44,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        borderWidth: 1,
        borderStyle: 'dashed',
        borderColor: active ? c.confirm : c.paperEdge,
        backgroundColor: c.paperRecessed,
        borderRadius: theme.radius.md,
        paddingVertical: 12,
        paddingHorizontal: 10,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {busy && <ActivityIndicator color={c.ink} />}
      <Text style={{ color: active ? c.confirm : c.ink, fontSize: 14 }}>{label}</Text>
    </Pressable>
  );
}

// A free-text answer that also accepts speech and handwriting. Voice is transcribed on-device
// (live); a photo is transcribed server-side. Either way the text lands in the editable field,
// so confirming/correcting it IS the confirm step the substrate promises — we grade what the
// student confirms, never the raw machine guess.
export function WrittenAnswer({
  value,
  onChangeText,
  onSubmit,
  onSnapPaper,
  transcribing,
  paperHint,
  rows = 4,
  submitLabel = 'Submit',
  placeholder = 'Type your answer…',
}: Props) {
  const theme = useTheme();
  const { c } = theme;
  const voice = useVoiceDictation(value, onChangeText);

  return (
    <View style={{ gap: 10 }}>
      <Textarea rows={rows} value={value} onChangeText={onChangeText} placeholder={placeholder} />

      <View style={{ flexDirection: 'row', gap: 8 }}>
        <AssistButton
          label={voice.recognizing ? '● Listening — tap to stop' : '🎤 Speak'}
          onPress={voice.toggle}
          active={voice.recognizing}
        />
        <AssistButton
          label={transcribing ? 'Reading…' : '✎ Snap handwriting'}
          onPress={onSnapPaper}
          disabled={transcribing}
          busy={transcribing}
        />
      </View>

      {voice.error && <Text style={{ fontSize: theme.size.bodySm, color: c.stateShaky }}>{voice.error}</Text>}
      {paperHint && <Text style={{ fontSize: theme.size.bodySm, color: c.inkSecondary }}>{paperHint}</Text>}

      <Button label={submitLabel} disabled={value.trim().length === 0 || transcribing || voice.recognizing} onPress={onSubmit} />
    </View>
  );
}
