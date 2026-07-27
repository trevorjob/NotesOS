import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

const SUGGESTED = [
  'Why does glycolysis need no oxygen?',
  'What happens if the ETC is blocked?',
  'Compare aerobic vs anaerobic yield',
];

const TUTOR_REPLY =
  'Glycolysis runs entirely in the cytoplasm and only uses substrate-level phosphorylation — no electron acceptor like oxygen is needed at that step. The payoff (ΔG = ΔH − TΔS favorable) comes later, in the ETC, which does need oxygen as the final electron acceptor.';

const THINKING_DELAY_MS = 1400;

type ChatRole = 'you' | 'tutor';

interface ChatMessage {
  role: ChatRole;
  text: string;
}

interface AITutorChatProps {
  onBack: () => void;
  scope?: string;
}

export function AITutorChat({ onBack, scope = 'Cellular Respiration' }: AITutorChatProps) {
  const { c, font, size, trackingUtility } = useTheme();
  const [courseWide, setCourseWide] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);

  const ask = (question: string) => {
    if (!question.trim()) return;
    setMessages((m) => [...m, { role: 'you', text: question }]);
    setInput('');
    setThinking(true);
    setTimeout(() => {
      setThinking(false);
      setMessages((m) => [...m, { role: 'tutor', text: TUTOR_REPLY }]);
    }, THINKING_DELAY_MS);
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: c.paper }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={{ paddingHorizontal: 20, paddingTop: 18, paddingBottom: 10 }}>
        <Pressable onPress={onBack} style={{ minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>← Note</Text>
        </Pressable>
        <Text style={{ fontFamily: font.display, fontSize: size.display3, marginTop: 4, color: c.ink }}>Ask the tutor</Text>
        <Pressable onPress={() => setCourseWide((v) => !v)} style={{ marginTop: 6, minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ fontFamily: font.utility, fontSize: size.caption, letterSpacing: trackingUtility(size.caption), textTransform: 'uppercase', color: c.confirm }}>
            {courseWide ? 'Course-wide · switch to this topic' : `${scope} · switch to course-wide`}
          </Text>
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingVertical: 10, gap: 16 }} style={{ flex: 1 }}>
        {messages.length === 0 && (
          <View>
            <Text style={{ color: c.inkSecondary, fontSize: size.bodySm, marginBottom: 10 }}>
              Grounded in your own materials — not the open web.
            </Text>
            {SUGGESTED.map((s) => (
              <Pressable
                key={s}
                onPress={() => ask(s)}
                style={{ paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: c.paperEdge, minHeight: 44, justifyContent: 'center' }}
              >
                <Text style={{ color: c.confirm, textDecorationLine: 'underline' }}>{s}</Text>
              </Pressable>
            ))}
          </View>
        )}

        {messages.map((m, i) => (
          <View
            key={i}
            style={
              m.role === 'you'
                ? { alignSelf: 'flex-end', maxWidth: '85%' }
                : { alignSelf: 'flex-start', maxWidth: '90%', borderLeftWidth: 2, borderLeftColor: c.paperEdge, paddingLeft: 12 }
            }
          >
            <Text
              style={{
                fontFamily: font.utility,
                fontSize: size.caption,
                letterSpacing: trackingUtility(size.caption),
                textTransform: 'uppercase',
                color: c.inkTertiary,
                marginBottom: 4,
                textAlign: m.role === 'you' ? 'right' : 'left',
              }}
            >
              {m.role === 'you' ? 'You' : 'Tutor'}
            </Text>
            <Text style={{ fontSize: size.body, lineHeight: size.body * 1.55, color: c.ink, textAlign: m.role === 'you' ? 'right' : 'left' }}>
              {m.text}
            </Text>
          </View>
        ))}

        {thinking && (
          <View style={{ alignSelf: 'flex-start', borderLeftWidth: 2, borderLeftColor: c.paperEdge, paddingLeft: 12 }}>
            <Text style={{ color: c.inkTertiary, fontSize: size.bodySm }}>Thinking…</Text>
          </View>
        )}
      </ScrollView>

      <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 20, paddingTop: 10, paddingBottom: 20, borderTopWidth: 1, borderTopColor: c.paperEdge }}>
        <View style={{ flex: 1 }}>
          <Input value={input} onChangeText={setInput} placeholder="Ask about this topic…" />
        </View>
        <Button label="→" onPress={() => ask(input)} size="sm" />
      </View>
    </KeyboardAvoidingView>
  );
}
