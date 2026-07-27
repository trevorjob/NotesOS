import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';
import { Sheet } from '@/components/ui/Sheet';
import { Button } from '@/components/ui/Button';

const REASONS = ['Inaccurate', 'Inappropriate', 'Spam or off-topic', 'Something else'];

type Stage = 'reasons' | 'done';

interface ReportSheetProps {
  onClose: () => void;
}

export function ReportSheet({ onClose }: ReportSheetProps) {
  const { c, font, size } = useTheme();
  const [stage, setStage] = useState<Stage>('reasons');
  const [reason, setReason] = useState<string | null>(null);

  return (
    <Sheet open onClose={onClose} title={stage === 'reasons' ? 'Report this' : undefined}>
      {stage === 'reasons' ? (
        <>
          <Text style={{ color: c.inkTertiary, fontSize: size.caption, marginBottom: 14 }}>
            Anonymous — the uploader won’t know it was you.
          </Text>
          {REASONS.map((r) => (
            <Pressable
              key={r}
              onPress={() => setReason(r)}
              style={{
                paddingVertical: 12,
                borderBottomWidth: 1,
                borderBottomColor: c.paperEdge,
                minHeight: 44,
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <Text style={{ color: c.ink, fontSize: size.body }}>{r}</Text>
              {reason === r && <Text style={{ color: c.confirm }}>✓</Text>}
            </Pressable>
          ))}
          <Button
            label="Submit report"
            disabled={!reason}
            onPress={() => setStage('done')}
            style={{ width: '100%', marginTop: 14 }}
          />
        </>
      ) : (
        <View style={{ alignItems: 'center', paddingVertical: 10 }}>
          <Text style={{ fontFamily: font.display, fontSize: size.display3, marginBottom: 8, color: c.ink }}>Reported.</Text>
          <Text style={{ color: c.inkSecondary, fontSize: size.bodySm, marginBottom: 16, textAlign: 'center' }}>
            Held out of the shared note pending review — no outcome loop back to you.
          </Text>
          <Button label="Close" variant="secondary" onPress={onClose} />
        </View>
      )}
    </Sheet>
  );
}
