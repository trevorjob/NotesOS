'use client';

import { useState } from 'react';
import { TabBar, Tab } from '@/components/ui/TabBar';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';

interface Topic {
  id: string;
  title: string;
  weekNumber?: number;
}

interface GenerateTestFormProps {
  topics: Topic[];
  onGenerate: (config: {
    topicIds: string[];
    questionCount: number;
    difficulty: string;
    questionTypes: string[];
  }) => void;
  loading?: boolean;
  className?: string;
}

const FORMAT_TABS: Tab[] = [
  { id: 'mixed',        label: 'Mixed' },
  { id: 'mcq',          label: 'MCQ' },
  { id: 'short_answer', label: 'Short Answer' },
];

const DIFFICULTY_TABS: Tab[] = [
  { id: 'easy',   label: 'Easy' },
  { id: 'medium', label: 'Medium' },
  { id: 'hard',   label: 'Hard' },
];

const COUNTS = [5, 10, 15, 20];

export function GenerateTestForm({ topics, onGenerate, loading = false, className = '' }: GenerateTestFormProps) {
  const [selectedTopics, setSelectedTopics] = useState<string[]>(topics.map((t) => t.id));
  const [count, setCount] = useState(10);
  const [format, setFormat] = useState('mixed');
  const [difficulty, setDifficulty] = useState('medium');

  const toggleTopic = (id: string) => {
    setSelectedTopics((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    );
  };

  const handleSubmit = () => {
    const qTypes =
      format === 'mixed'        ? ['mcq', 'short_answer'] :
      format === 'mcq'          ? ['mcq'] :
      ['short_answer'];

    onGenerate({
      topicIds: selectedTopics,
      questionCount: count,
      difficulty,
      questionTypes: qTypes,
    });
  };

  return (
    <div className={`flex flex-col gap-6 ${className}`}>
      {/* Topics */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Topics</h3>
          <button
            onClick={() =>
              setSelectedTopics(
                selectedTopics.length === topics.length ? [] : topics.map((t) => t.id)
              )
            }
            className="text-xs text-[var(--color-primary)] hover:underline"
          >
            {selectedTopics.length === topics.length ? 'Deselect all' : 'Select all'}
          </button>
        </div>
        <div className="flex flex-col gap-2">
          {topics.map((topic) => {
            const selected = selectedTopics.includes(topic.id);
            return (
              <button
                key={topic.id}
                onClick={() => toggleTopic(topic.id)}
                className={`
                  flex items-center gap-3 px-4 py-3 rounded-xl text-left
                  border transition-all duration-150
                  ${selected
                    ? 'border-[var(--color-primary)] bg-[var(--color-primary-muted)] text-[var(--text-primary)]'
                    : 'border-[var(--border-base)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:border-[var(--color-primary-muted)]'
                  }
                `}
              >
                <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 ${selected ? 'bg-[var(--color-primary)]' : 'border-2 border-[var(--border-base)]'}`}>
                  {selected && <Icon name="check" size="xs" className="text-white" />}
                </div>
                {topic.weekNumber !== undefined && (
                  <span className="text-[10px] font-bold uppercase text-[var(--text-tertiary)]">W{topic.weekNumber}</span>
                )}
                <span className="text-sm font-medium flex-1">{topic.title}</span>
              </button>
            );
          })}
        </div>
      </section>

      {/* Question count */}
      <section>
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Questions</h3>
        <div className="flex gap-2">
          {COUNTS.map((c) => (
            <button
              key={c}
              onClick={() => setCount(c)}
              className={`
                flex-1 h-11 rounded-xl text-sm font-bold border transition-all
                ${count === c
                  ? 'bg-[var(--color-primary)] text-white border-[var(--color-primary)]'
                  : 'bg-[var(--bg-sunken)] text-[var(--text-secondary)] border-[var(--border-base)] hover:border-[var(--color-primary-muted)]'
                }
              `}
            >
              {c}
            </button>
          ))}
        </div>
      </section>

      {/* Format */}
      <section>
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Format</h3>
        <TabBar tabs={FORMAT_TABS} active={format} onChange={setFormat} variant="pill" />
      </section>

      {/* Difficulty */}
      <section>
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Difficulty</h3>
        <TabBar tabs={DIFFICULTY_TABS} active={difficulty} onChange={setDifficulty} variant="pill" />
      </section>

      {/* Generate button */}
      <Button
        variant="primary"
        size="lg"
        onClick={handleSubmit}
        loading={loading}
        disabled={selectedTopics.length === 0}
        iconLeft="auto_awesome"
        fullWidth
      >
        Generate Test
      </Button>
    </div>
  );
}
