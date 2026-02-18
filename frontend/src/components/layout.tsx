/**
 * NotesOS Navigation Components
 * Frosted glass navigation bar with functional course dropdown switcher
 */

'use client';

import { ReactNode, useState, useEffect, useRef } from 'react';
import { ChevronDown, User, Flame } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { useRouter } from 'next/navigation';

// ═══════════════════════════════════════════════════════════════════════
// GlassNav — Fixed frosted navigation bar with course dropdown
// ═══════════════════════════════════════════════════════════════════════

interface GlassNavProps {
    currentCourse?: {
        id: string;
        code: string;
        name: string;
    };
    onCourseSwitch?: () => void;
    onProfileClick?: () => void;
    streak?: number;
}

export function GlassNav({ currentCourse, onCourseSwitch, onProfileClick, streak }: GlassNavProps) {
    const [showCourseDropdown, setShowCourseDropdown] = useState(false);
    const { courses, fetchCourses } = useCourseStore();
    const router = useRouter();
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Load courses for dropdown
    useEffect(() => {
        fetchCourses();
    }, [fetchCourses]);

    // Close dropdown on outside click
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setShowCourseDropdown(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleCourseSelect = (courseId: string) => {
        setShowCourseDropdown(false);
        router.push(`/courses/${courseId}`);
    };

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
                    <div className="relative" ref={dropdownRef}>
                        <button
                            onClick={() => setShowCourseDropdown(!showCourseDropdown)}
                            className="flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors px-3 py-2 rounded-lg hover:bg-[var(--bg-sunken)]"
                        >
                            <span className="hidden md:inline">{currentCourse.code}</span>
                            <ChevronDown className={`w-4 h-4 transition-transform ${showCourseDropdown ? 'rotate-180' : ''}`} />
                        </button>

                        {/* Dropdown */}
                        {showCourseDropdown && (
                            <div className="absolute top-full mt-2 left-1/2 -translate-x-1/2 w-72 glass-nav rounded-lg border border-[var(--glass-border)] shadow-xl overflow-hidden">
                                <div className="max-h-80 overflow-y-auto">
                                    {courses.map((course) => (
                                        <button
                                            key={course.id}
                                            onClick={() => handleCourseSelect(course.id)}
                                            className={`w-full px-4 py-3 text-left hover:bg-[var(--bg-sunken)] transition-colors border-b border-[var(--glass-border)] last:border-0 ${course.id === currentCourse?.id ? 'bg-[var(--accent-primary)]/5' : ''
                                                }`}
                                        >
                                            <div className="text-sm font-medium text-[var(--text-primary)]">
                                                {course.code} · {course.name}
                                            </div>
                                            {course.semester && (
                                                <div className="text-xs text-[var(--text-tertiary)] mt-0.5">
                                                    {course.semester}
                                                </div>
                                            )}
                                        </button>
                                    ))}
                                    {courses.length === 0 && (
                                        <div className="px-4 py-6 text-center text-sm text-[var(--text-tertiary)]">
                                            No courses yet
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* Right side — Streak + Profile */}
                <div className="flex items-center gap-4">
                    {streak !== undefined && (
                        <button className="flex items-center gap-1.5 text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
                            <Flame className="w-4 h-4" />
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
        id: string;
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
