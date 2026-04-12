'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

type Tone = 'encouraging' | 'direct' | 'humorous';
type Emoji = 'none' | 'moderate' | 'heavy';
type Style = 'concise' | 'detailed' | 'visual';

const TONE_OPTIONS: { value: Tone; label: string; desc: string }[] = [
  { value: 'encouraging', label: 'Encouraging', desc: 'Warm & supportive' },
  { value: 'direct', label: 'Direct', desc: 'Straight to the point' },
  { value: 'humorous', label: 'Humorous', desc: 'Light-hearted & fun' },
];

const STYLE_OPTIONS: { value: Style; label: string; desc: string }[] = [
  { value: 'concise', label: 'Concise', desc: 'Short and clear' },
  { value: 'detailed', label: 'Detailed', desc: 'Thorough explanations' },
  { value: 'visual', label: 'Visual', desc: 'Diagrams & examples' },
];

const EMOJI_OPTIONS: { value: Emoji; label: string }[] = [
  { value: 'none', label: 'None' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'heavy', label: 'Heavy' },
];

function OptionCard<T extends string>({
  value,
  label,
  desc,
  selected,
  onSelect,
}: {
  value: T;
  label: string;
  desc?: string;
  selected: boolean;
  onSelect: (v: T) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(value)}
      className={`flex-1 rounded-lg border px-3 py-2.5 text-left transition-colors ${
        selected
          ? 'border-[#1a1917] bg-[#1a1917] text-white'
          : 'border-[#dedad4] bg-white text-[#1a1917] hover:border-[#9e9a94]'
      }`}
    >
      <p className="text-sm font-medium">{label}</p>
      {desc && <p className={`text-xs mt-0.5 ${selected ? 'text-[#c8c4be]' : 'text-[#6b6762]'}`}>{desc}</p>}
    </button>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#f0eeea] flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-[#1a1917] border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <RegisterPageInner />
    </Suspense>
  );
}

function RegisterPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const inviteCode = searchParams.get('code');
  const { register, updatePersonality, isLoading, error, clearError } = useAuthStore();

  const [step, setStep] = useState(1);

  // Step 1 fields
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // Step 2 fields
  const [tone, setTone] = useState<Tone>('encouraging');
  const [style, setStyle] = useState<Style>('detailed');
  const [emoji, setEmoji] = useState<Emoji>('moderate');

  const [saving, setSaving] = useState(false);

  async function handleStep1(e: React.FormEvent) {
    e.preventDefault();
    clearError();
    try {
      await register({ full_name: name, email, password, ...(inviteCode ? { invite_code: inviteCode } : {}) });
      setStep(2);
    } catch {
      // error already in store
    }
  }

  async function handleFinish() {
    setSaving(true);
    try {
      await updatePersonality({ tone, explanation_style: style, emoji_usage: emoji });
    } catch {
      // non-critical — proceed anyway
    } finally {
      setSaving(false);
      router.replace('/home');
    }
  }

  return (
    <div className="min-h-screen bg-[#f0eeea] flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-white rounded-2xl border border-[#dedad4] p-8 shadow-sm">

        {/* Step dots */}
        <div className="flex items-center gap-1.5 mb-6">
          {[1, 2].map((n) => (
            <span
              key={n}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                n === step ? 'w-6 bg-[#1a1917]' : 'w-1.5 bg-[#dedad4]'
              }`}
            />
          ))}
        </div>

        {step === 1 && (
          <>
            <h1 className="text-xl font-semibold text-[#1a1917] mb-1">Create account</h1>
            <p className="text-sm text-[#6b6762] mb-6">Start your learning journey</p>

            <form onSubmit={handleStep1} className="space-y-4">
              <Input
                label="Username"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Joker123"
                autoComplete="name"
                required
              />
              <Input
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
              <Input
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min. 8 characters"
                autoComplete="new-password"
                required
              />

              {error && <p className="text-sm text-[#dc2626]">{error}</p>}

              <Button type="submit" className="w-full" loading={isLoading}>
                Continue
              </Button>
            </form>

            <p className="mt-5 text-center text-sm text-[#6b6762]">
              Already have an account?{' '}
              <a href="/login" className="text-[#1a1917] font-medium underline underline-offset-2">
                Sign in
              </a>
            </p>
          </>
        )}

        {step === 2 && (
          <>
            <h1 className="text-xl font-semibold text-[#1a1917] mb-1">Personalise your AI</h1>
            <p className="text-sm text-[#6b6762] mb-6">How should NotesOS talk to you?</p>

            <div className="space-y-5">
              {/* Tone */}
              <div>
                <p className="text-xs font-medium text-[#6b6762] mb-2 uppercase tracking-wide">Tone</p>
                <div className="flex gap-2">
                  {TONE_OPTIONS.map((o) => (
                    <OptionCard key={o.value} {...o} selected={tone === o.value} onSelect={setTone} />
                  ))}
                </div>
              </div>

              {/* Explanation style */}
              <div>
                <p className="text-xs font-medium text-[#6b6762] mb-2 uppercase tracking-wide">Explanation Style</p>
                <div className="flex gap-2">
                  {STYLE_OPTIONS.map((o) => (
                    <OptionCard key={o.value} {...o} selected={style === o.value} onSelect={setStyle} />
                  ))}
                </div>
              </div>

              {/* Emoji */}
              <div>
                <p className="text-xs font-medium text-[#6b6762] mb-2 uppercase tracking-wide">Emoji Usage</p>
                <div className="flex gap-2">
                  {EMOJI_OPTIONS.map((o) => (
                    <OptionCard key={o.value} label={o.label} value={o.value} selected={emoji === o.value} onSelect={setEmoji} />
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-6 flex flex-col gap-2">
              <Button className="w-full" loading={saving} onClick={handleFinish}>
                Start studying
              </Button>
              <Button variant="ghost" className="w-full" onClick={() => router.replace('/home')}>
                Skip for now
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
