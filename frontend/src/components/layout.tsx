/**
 * NotesOS Navigation Components
 * Frosted glass navigation bar with course switcher
 */

'use client';

import { ReactNode } from 'react';
import { ChevronDown, User } from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════════
// GlassNav — Fixed frosted navigation bar
// ═══════════════════════════════════════════════════════════════════════

interface GlassNavProps {
    currentCourse?: {
        code: string;
        name: string;
    };
    onCourseSwitch?: () => void;
    onProfileClick?: () => void;
    streak?: number;
}

export function GlassNav({ currentCourse, onCourseSwitch, onProfileClick, streak }: GlassNavProps) {
    return (
        <nav className="glass-nav fixed top-0 w-full h-16 px-8 md:px-20 z-50">
            <div className="flex items-center justify-between h-full max-w-[1920px] mx-auto">
                {/* Logo */}
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-[var(--accent-primary)] rounded-lg" />
                    <span className="text-lg font-medium text-[var(--text-primary)]">
                        NotesOS
                    </span>
                </div>

                {/* Course Switcher (center) */}
                {currentCourse && (
                    <button
                        onClick={onCourseSwitch}
                        className="flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                    >
                        <span className="hidden md:inline">{currentCourse.code}</span>
                        <ChevronDown className="w-4 h-4" />
                    </button>
                )}

                {/* Right side — Streak + Profile */}
                <div className="flex items-center gap-4">
                    {streak !== undefined && (
                        <button className="flex items-center gap-1.5 text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
                            <span>🔥</span>
                            <span>{streak}</span>
                        </button>
                    )}

                    <button
                        onClick={onProfileClick}
                        className="w-9 h-9 rounded-full bg-[var(--bg-sunken)] flex items-center justify-center text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
                    >
                        <User className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </nav>
    );
}

// ═══════════════════════════════════════════════════════════════════════
// MainLayout — Page layout with nav + content
// ═══════════════════════════════════════════════════════════════════════

interface MainLayoutProps {
    children: ReactNode;
    currentCourse?: {
        code: string;
        name: string;
    };
    streak?: number;
}

export function MainLayout({ children, currentCourse, streak }: MainLayoutProps) {
    return (
        <div className="min-h-screen bg-[var(--bg-base)]">
            <GlassNav currentCourse={currentCourse} streak={streak} />
            <main className="pt-16">
                {children}
            </main>
        </div>
    );
}
