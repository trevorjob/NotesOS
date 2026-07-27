import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

interface QuickSwitcherContextValue {
  open: boolean;
  openSwitcher: () => void;
  closeSwitcher: () => void;
}

const QuickSwitcherContext = createContext<QuickSwitcherContextValue | null>(null);

export function QuickSwitcherProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const openSwitcher = useCallback(() => setOpen(true), []);
  const closeSwitcher = useCallback(() => setOpen(false), []);
  const value = useMemo(() => ({ open, openSwitcher, closeSwitcher }), [open, openSwitcher, closeSwitcher]);

  return <QuickSwitcherContext.Provider value={value}>{children}</QuickSwitcherContext.Provider>;
}

export function useQuickSwitcher() {
  const ctx = useContext(QuickSwitcherContext);
  if (!ctx) throw new Error('useQuickSwitcher must be used within QuickSwitcherProvider');
  return ctx;
}
