import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { api } from '@/lib/api';
import { setTokens } from '@/lib/auth';
import { canonicalPhone } from '@/lib/phone';

type Mode = 'login' | 'register';
type Stage = 'form' | 'success';

export default function LoginScreen() {
  const { c, font, size, space } = useTheme();
  const [mode, setMode] = useState<Mode>('login');
  const [stage, setStage] = useState<Stage>('form');
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const path = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      // Canonicalise to E.164 (device-region aware) so the stored identity — and
      // therefore the contact-match hash — is region-independent and consistent
      // across login/register, whatever format the user typed. See lib/phone.ts.
      const phoneValue = canonicalPhone(phone) || phone.trim();
      const payload =
        mode === 'login'
          ? { phone: phoneValue, password }
          : { phone: phoneValue, password, full_name: name };
      const { data } = await api.post(path, payload);
      await setTokens({ accessToken: data.access_token, refreshToken: data.refresh_token });
      setStage('success');
    } catch (err) {
      if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') {
        setError(err.response.data.detail);
      } else {
        setError('Something went wrong. Try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const continueAfterAuth = () => {
    router.replace(mode === 'register' ? '/onboarding' : '/home');
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ flex: 1, paddingHorizontal: space.gutterPage, paddingVertical: 40 }}>
        <Text style={{ fontFamily: font.display, fontSize: size.display2, color: c.ink, marginBottom: 32 }}>
          NotesOS
        </Text>

        {stage === 'form' && (
          <View style={{ gap: 16 }}>
            <Text style={{ fontFamily: font.display, fontSize: size.display3, color: c.ink }}>
              {mode === 'login' ? 'Welcome back' : 'Create your account'}
            </Text>

            {mode === 'register' && (
              <Input label="Name" value={name} onChangeText={setName} placeholder="Ada Obi" />
            )}

            <Input label="Phone number" value={phone} onChangeText={setPhone} placeholder="+234 800 000 0000" keyboardType="phone-pad" />
            <Input label="Password" value={password} onChangeText={setPassword} placeholder="••••••••" secureTextEntry />

            {error && (
              <Text style={{ color: c.stateShaky, fontSize: size.bodySm }}>{error}</Text>
            )}

            <Button
              label={submitting ? 'Please wait…' : 'Continue'}
              onPress={submit}
              disabled={submitting || !phone || !password || (mode === 'register' && !name)}
              style={{ marginTop: 6 }}
            />

            <Pressable onPress={() => setMode(mode === 'login' ? 'register' : 'login')} style={{ marginTop: 12, minHeight: 44, justifyContent: 'center' }}>
              <Text style={{ fontSize: size.bodySm, color: c.confirm, textDecorationLine: 'underline' }}>
                {mode === 'login' ? 'New here? Create an account' : 'Already have an account? Log in'}
              </Text>
            </Pressable>
          </View>
        )}

        {stage === 'success' && (
          <View style={{ paddingTop: 60, gap: 14, alignItems: 'center' }}>
            <Text style={{ fontFamily: font.display, fontSize: size.display2, color: c.ink, textAlign: 'center' }}>
              You’re in.
            </Text>
            <Button label="Continue" onPress={continueAfterAuth} />
          </View>
        )}
      </View>
    </SafeAreaView>
  );
}
