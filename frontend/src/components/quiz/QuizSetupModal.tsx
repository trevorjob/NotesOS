'use client';

import { useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';

const COUNT_OPTIONS = [5, 10, 15, 20];
const TYPE_OPTIONS = [
  { value: 'mixed', label: 'Mixed' },
  { value: 'mcq', label: 'MCQ' },
  { value: 'short_answer', label: 'Short Answer' },
  { value: 'definition', label: 'Definition' },
];

interface QuizSetupModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStart: (config: { count: number; types: string[] }) => void;
  loading?: boolean;
}

function Chip<T extends string | number>({
  value,
  label,
  selected,
  onSelect,
}: {
  value: T;
  label: string;
  selected: boolean;
  onSelect: (v: T) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(value)}
      className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
        selected
          ? 'border-[#1a1917] bg-[#1a1917] text-white'
          : 'border-[#dedad4] text-[#1a1917] hover:border-[#9e9a94]'
      }`}
    >
      {label}
    </button>
  );
}

export function QuizSetupModal({ isOpen, onClose, onStart, loading }: QuizSetupModalProps) {
  const [count, setCount] = useState(10);
  const [type, setType] = useState('mixed');

  function handleStart() {
    const types = type === 'mixed' ? ['mcq', 'short_answer'] : [type];
    onStart({ count, types });
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Quiz Setup">
      <div className="space-y-5">
        {/* Count */}
        <div>
          <p className="text-xs font-medium text-[#6b6762] uppercase tracking-wide mb-2">Number of Questions</p>
          <div className="flex gap-2">
            {COUNT_OPTIONS.map((n) => (
              <Chip key={n} value={n} label={String(n)} selected={count === n} onSelect={setCount} />
            ))}
          </div>
        </div>

        {/* Type */}
        <div>
          <p className="text-xs font-medium text-[#6b6762] uppercase tracking-wide mb-2">Question Type</p>
          <div className="flex flex-wrap gap-2">
            {TYPE_OPTIONS.map((o) => (
              <Chip key={o.value} value={o.value} label={o.label} selected={type === o.value} onSelect={setType} />
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" loading={loading} onClick={handleStart}>Start Quiz</Button>
        </div>
      </div>
    </Modal>
  );
}
