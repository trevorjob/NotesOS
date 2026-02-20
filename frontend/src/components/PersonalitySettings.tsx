/**
 * Study personality settings: tone, emoji usage, explanation style
 */

'use client';

import { useState, useEffect } from 'react';
import { useAuthStore } from '@/stores/auth';
import { GlassCard, Button } from '@/components/ui';

export function PersonalitySettings() {
    const { user, updatePersonality } = useAuthStore();
    const [tone, setTone] = useState<string>('encouraging');
    const [emojiUsage, setEmojiUsage] = useState<string>('moderate');
    const [explanationStyle, setExplanationStyle] = useState<string>('detailed');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        const p = user?.study_personality;
        if (p) {
            if (p.tone) setTone(p.tone);
            if (p.emoji_usage) setEmojiUsage(p.emoji_usage);
            if (p.explanation_style) setExplanationStyle(p.explanation_style);
        }
    }, [user?.study_personality]);

    const handleSave = async () => {
        setSaving(true);
        try {
            await updatePersonality({
                tone: tone as 'encouraging' | 'direct' | 'humorous',
                emoji_usage: emojiUsage as 'none' | 'moderate' | 'heavy',
                explanation_style: explanationStyle as 'concise' | 'detailed' | 'visual',
            });
        } finally {
            setSaving(false);
        }
    };

    return (
        <GlassCard>
            <h2 className="text-lg font-medium text-[var(--text-primary)] mb-4">Study personality</h2>
            <p className="text-sm text-[var(--text-tertiary)] mb-6">
                Adjust how the AI study partner talks to you.
            </p>
            <div className="space-y-6">
                <div>
                    <label className="block text-sm font-medium text-[var(--text-primary)] mb-2">Tone</label>
                    <select
                        value={tone}
                        onChange={(e) => setTone(e.target.value)}
                        className="w-full px-4 py-2.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded-lg text-sm text-[var(--text-primary)]"
                    >
                        <option value="encouraging">Encouraging</option>
                        <option value="direct">Direct</option>
                        <option value="humorous">Humorous</option>
                    </select>
                </div>
                <div>
                    <label className="block text-sm font-medium text-[var(--text-primary)] mb-2">Emoji usage</label>
                    <select
                        value={emojiUsage}
                        onChange={(e) => setEmojiUsage(e.target.value)}
                        className="w-full px-4 py-2.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded-lg text-sm text-[var(--text-primary)]"
                    >
                        <option value="none">None</option>
                        <option value="moderate">Moderate</option>
                        <option value="heavy">Heavy</option>
                    </select>
                </div>
                <div>
                    <label className="block text-sm font-medium text-[var(--text-primary)] mb-2">Explanation style</label>
                    <select
                        value={explanationStyle}
                        onChange={(e) => setExplanationStyle(e.target.value)}
                        className="w-full px-4 py-2.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded-lg text-sm text-[var(--text-primary)]"
                    >
                        <option value="concise">Concise</option>
                        <option value="detailed">Detailed</option>
                        <option value="visual">Visual</option>
                    </select>
                </div>
                <Button variant="primary" onClick={handleSave} disabled={saving}>
                    {saving ? 'Saving...' : 'Save preferences'}
                </Button>
            </div>
        </GlassCard>
    );
}
