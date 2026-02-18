/**
 * NotesOS Core UI Components
 * Warm glassmorphism design with minimal color palette
 */

import { ReactNode, ButtonHTMLAttributes, InputHTMLAttributes, forwardRef } from 'react';

// ═══════════════════════════════════════════════════════════════════════
// GlassCard — Base container with warm frosted glass effect
// ═══════════════════════════════════════════════════════════════════════

interface GlassCardProps {
    children: ReactNode;
    className?: string;
    hover?: boolean;
}

export function GlassCard({ children, className = '', hover = false }: GlassCardProps) {
    return (
        <div
            className={`glass-card p-6 ${hover ? 'transition-all duration-200 hover:border-[#D6D3D1] hover:-translate-y-0.5' : ''
                } ${className}`}
        >
            {children}
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════
// Button — Primary (walnut), Secondary (outlined), Ghost, Icon
// ═══════════════════════════════════════════════════════════════════════

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'ghost' | 'icon';
    size?: 'sm' | 'md' | 'lg';
    children: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    ({ variant = 'primary', size = 'md', className = '', children, ...props }, ref) => {
        const baseStyles = 'rounded-lg font-medium transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed';

        const variantStyles = {
            primary: 'bg-[var(--accent-primary)] text-[var(--bg-elevated)] hover:bg-[var(--accent-hover)] active:translate-y-0',
            secondary: 'border border-[#D6D3D1] text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] active:translate-y-0',
            ghost: 'text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] active:translate-y-0',
            icon: 'text-[var(--text-tertiary)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text-secondary)] rounded-lg p-2',
        };

        const sizeStyles = {
            sm: 'px-4 py-2 text-sm',
            md: 'px-6 py-2.5 text-sm',
            lg: 'px-8 py-3 text-base',
        };

        return (
            <button
                ref={ref}
                className={`${baseStyles} ${variantStyles[variant]} ${variant !== 'icon' ? sizeStyles[size] : ''} ${className}`}
                {...props}
            >
                {children}
            </button>
        );
    }
);

Button.displayName = 'Button';

// ═══════════════════════════════════════════════════════════════════════
// Input — Text input with warm sand background
// ═══════════════════════════════════════════════════════════════════════

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
    label?: string;
    error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
    ({ label, error, className = '', ...props }, ref) => {
        return (
            <div className="flex flex-col gap-1.5">
                {label && (
                    <label className="text-sm font-medium text-[var(--text-primary)]">
                        {label}
                    </label>
                )}
                <input
                    ref={ref}
                    className={`
            px-4 py-2.5 
            bg-[var(--bg-sunken)] 
            border-0 
            rounded-lg
            text-base text-[var(--text-primary)]
            placeholder:text-[var(--text-tertiary)]
            focus:outline-none 
            focus:ring-2 
            focus:ring-[var(--accent-primary)]
            transition-all
            ${error ? 'ring-2 ring-[var(--error)]' : ''}
            ${className}
          `}
                    {...props}
                />
                {error && (
                    <span className="text-sm text-[var(--error)]">{error}</span>
                )}
            </div>
        );
    }
);

Input.displayName = 'Input';

// ═══════════════════════════════════════════════════════════════════════
// Badge — Minimal status indicator
// ═══════════════════════════════════════════════════════════════════════

interface BadgeProps {
    children: ReactNode;
    variant?: 'default' | 'success' | 'error';
    className?: string;
}

export function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
    const variantStyles = {
        default: 'bg-[var(--bg-sunken)] text-[var(--text-secondary)]',
        success: 'bg-[#6B8F71]/10 text-[#6B8F71]',
        error: 'bg-[#C75C5C]/10 text-[#C75C5C]',
    };

    return (
        <span
            className={`
        inline-flex items-center gap-1.5
        px-2.5 py-1
        rounded-md
        text-xs font-medium
        ${variantStyles[variant]}
        ${className}
      `}
        >
            {children}
        </span>
    );
}

// ═══════════════════════════════════════════════════════════════════════
// PageHeader — Consistent page titles
// ═══════════════════════════════════════════════════════════════════════

interface PageHeaderProps {
    title: string;
    subtitle?: string;
    action?: ReactNode;
    icon?: ReactNode;
}

export function PageHeader({ title, subtitle, action, icon }: PageHeaderProps) {
    return (
        <div className="flex items-start justify-between mb-12">
            <div>
                <div className="flex items-center gap-3 mb-3">
                    {icon && <div className="text-[var(--accent-primary)]">{icon}</div>}
                    <h1 className="text-4xl font-semibold text-[var(--text-primary)]">
                        {title}
                    </h1>
                </div>
                {subtitle && (
                    <p className="text-base text-[var(--text-tertiary)]">{subtitle}</p>
                )}
            </div>
            {action && <div>{action}</div>}
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════
// Skeleton — Loading placeholder
// ═══════════════════════════════════════════════════════════════════════

interface SkeletonProps {
    className?: string;
}

export function Skeleton({ className = '' }: SkeletonProps) {
    return (
        <div
            className={`animate-pulse bg-[var(--bg-sunken)] rounded ${className}`}
        />
    );
}
