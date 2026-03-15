'use client';

import { Button } from './Button';
import { AutoSaveIndicator } from '@/components/feedback/AutoSaveIndicator';

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

interface TestNavButtonsProps {
  onPrev?: () => void;
  onNext?: () => void;
  onSubmit?: () => void;
  hasPrev?: boolean;
  hasNext?: boolean;
  isLast?: boolean;
  saveState?: SaveState;
  submitting?: boolean;
}

export function TestNavButtons({
  onPrev,
  onNext,
  onSubmit,
  hasPrev = true,
  hasNext = true,
  isLast = false,
  saveState = 'idle',
  submitting = false,
}: TestNavButtonsProps) {
  return (
    <div className="flex items-center justify-between gap-4 p-4">
      <Button
        variant="secondary"
        size="md"
        onClick={onPrev}
        disabled={!hasPrev}
        iconLeft="arrow_back"
      >
        Previous
      </Button>

      <AutoSaveIndicator state={saveState} />

      {isLast ? (
        <Button
          variant="primary"
          size="md"
          onClick={onSubmit}
          loading={submitting}
          iconRight="check"
        >
          Submit
        </Button>
      ) : (
        <Button
          variant="primary"
          size="md"
          onClick={onNext}
          disabled={!hasNext}
          iconRight="arrow_forward"
        >
          Next
        </Button>
      )}
    </div>
  );
}
