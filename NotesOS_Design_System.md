# NotesOS Design System
## Premium, Minimalist UI/UX Specification

**Design Philosophy:** "Intentional simplicity. Every pixel matters."

---

## 🎨 Visual Identity

### Core Principles

1. **Quiet Confidence** - Let content breathe. UI fades into background.
2. **Surgical Precision** - Perfect alignment, consistent spacing, deliberate hierarchy.
3. **Material Honesty** - Subtle depth through glassmorphism, not gradients.
4. **Restrained Motion** - Animations feel physical, not decorative.

### Anti-Patterns to Avoid

❌ **Vibe-Coded Aesthetics:**
- Purple/pink gradients
- Excessive emojis in UI
- Rounded corners everywhere (looking at you, border-radius: 16px)
- Drop shadows on everything
- Colorful accent buttons

❌ **Generic SaaS:**
- Blue primary color
- Sans-serif everything
- Card-based layouts with shadows
- Dashboard with 6 colored metrics cards

✅ **What We're Actually Doing:**
- Monochromatic with surgical color use
- Glass morphism for depth
- Typography as primary design element
- Intentional white space
- Muted, sophisticated palette

---

## 🎨 Color System

### Primary Palette (Neutral-First)

```css
/* Background Layers */
--bg-base: #FAFAF9;           /* Warm white, not pure white */
--bg-elevated: #FFFFFF;        /* Pure white for cards */
--bg-overlay: rgba(250, 250, 249, 0.72);  /* Glass effect */

/* Surface Colors */
--surface-1: #F5F5F4;         /* Subtle elevation */
--surface-2: #E7E5E4;         /* Borders, dividers */
--surface-3: #D6D3D1;         /* Hover states */

/* Text Hierarchy */
--text-primary: #1C1917;      /* Almost black, not pure black */
--text-secondary: #57534E;    /* Body text, less emphasis */
--text-tertiary: #A8A29E;     /* Metadata, timestamps */
--text-disabled: #D6D3D1;     /* Disabled states */

/* Accent (Used Sparingly) */
--accent-primary: #18181B;    /* Zinc-900, for CTAs */
--accent-hover: #27272A;      /* Zinc-800 */
--accent-active: #3F3F46;     /* Zinc-700 */

/* Semantic Colors (Muted) */
--success: #059669;           /* Emerald-600, not bright green */
--warning: #D97706;           /* Amber-600, not yellow */
--error: #DC2626;             /* Red-600, not bright red */
--info: #0284C7;              /* Sky-600, not blue */

/* Glass Morphism */
--glass-bg: rgba(255, 255, 255, 0.7);
--glass-border: rgba(255, 255, 255, 0.18);
--glass-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);

/* Dark Mode (Optional, for later) */
--dark-bg-base: #18181B;
--dark-bg-elevated: #27272A;
--dark-text-primary: #FAFAF9;
```

### Color Usage Rules

1. **90% Neutral** - Most UI uses neutral colors
2. **5% Accent** - Black for primary actions only
3. **5% Semantic** - Success/error states only

**Never:**
- Colored backgrounds (no purple hero sections)
- Multiple accent colors (no blue + purple combo)
- Bright, saturated colors (everything is muted)

---

## 📐 Spacing System

### 8px Base Grid

```css
--space-1: 0.25rem;  /* 4px - Micro spacing */
--space-2: 0.5rem;   /* 8px - Tight */
--space-3: 0.75rem;  /* 12px - Compact */
--space-4: 1rem;     /* 16px - Default */
--space-5: 1.25rem;  /* 20px - Comfortable */
--space-6: 1.5rem;   /* 24px - Relaxed */
--space-8: 2rem;     /* 32px - Section spacing */
--space-10: 2.5rem;  /* 40px - Large gaps */
--space-12: 3rem;    /* 48px - Major sections */
--space-16: 4rem;    /* 64px - Hero spacing */
--space-20: 5rem;    /* 80px - Page margins */
--space-24: 6rem;    /* 96px - Dramatic spacing */
```

### Usage

- **Micro elements** (icon padding): 4px
- **Component padding**: 16px-24px
- **Section spacing**: 48px-64px
- **Page margins**: 80px-96px

**Golden Rule:** Everything aligns to 8px grid. No 13px margins.

---

## 🔤 Typography

### Font Stack

```css
/* Primary: Inter (clean, neutral, modern) */
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

/* Monospace: JetBrains Mono (for code, metadata) */
--font-mono: 'JetBrains Mono', 'SF Mono', Monaco, 'Cascadia Code', monospace;

/* Optional Serif (for long-form content) */
--font-serif: 'Crimson Pro', Georgia, 'Times New Roman', serif;
```

### Type Scale

```css
/* Display */
--text-5xl: 3rem;      /* 48px - Hero headlines */
--text-4xl: 2.25rem;   /* 36px - Page titles */
--text-3xl: 1.875rem;  /* 30px - Section headers */
--text-2xl: 1.5rem;    /* 24px - Card titles */

/* Body */
--text-xl: 1.25rem;    /* 20px - Large body */
--text-lg: 1.125rem;   /* 18px - Comfortable reading */
--text-base: 1rem;     /* 16px - Default */
--text-sm: 0.875rem;   /* 14px - Metadata */
--text-xs: 0.75rem;    /* 12px - Captions */

/* Font Weights */
--font-light: 300;
--font-normal: 400;
--font-medium: 500;    /* Use for emphasis, not bold */
--font-semibold: 600;  /* Headings only */
--font-bold: 700;      /* Almost never use */
```

### Typography Rules

1. **Line Height**
   - Headlines: 1.2
   - Body text: 1.6
   - Captions: 1.4

2. **Font Weight Hierarchy**
   - Display: 600 (semibold)
   - Headings: 500 (medium)
   - Body: 400 (normal)
   - Metadata: 400 (normal, but smaller + tertiary color)

3. **Never:**
   - All caps except for tiny labels (e.g., "BETA")
   - Multiple font weights on one line
   - Underlines (use color/weight for emphasis)

---

## 🧊 Glass Morphism Components

### Glass Card

```css
.glass-card {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.18);
  box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
  border-radius: 12px; /* Subtle, not excessive */
}
```

### Frosted Glass Navigation

```css
.glass-nav {
  background: rgba(250, 250, 249, 0.72);
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}
```

### Floating Glass Panel

```css
.glass-panel {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(30px) saturate(200%);
  -webkit-backdrop-filter: blur(30px) saturate(200%);
  border: 1px solid rgba(255, 255, 255, 0.3);
  box-shadow: 
    0 8px 32px 0 rgba(31, 38, 135, 0.07),
    inset 0 1px 0 0 rgba(255, 255, 255, 0.5);
  border-radius: 16px;
}
```

---

## 🎭 Component Design Patterns

### Navigation Bar

**Design:**
- Fixed top, frosted glass
- 64px height
- Logo left, user profile right
- Course switcher center
- Subtle bottom border (1px, rgba(0,0,0,0.06))

```tsx
<nav className="glass-nav fixed top-0 w-full h-16 px-20">
  <div className="flex items-center justify-between h-full">
    {/* Logo */}
    <div className="flex items-center gap-3">
      <div className="w-8 h-8 bg-zinc-900 rounded-lg" />
      <span className="text-lg font-medium text-zinc-900">NotesOS</span>
    </div>
    
    {/* Course Switcher */}
    <div className="flex items-center gap-2 text-sm text-zinc-600">
      <span>HIST 101</span>
      <ChevronDown className="w-4 h-4" />
    </div>
    
    {/* User */}
    <button className="w-9 h-9 rounded-full bg-zinc-200" />
  </div>
</nav>
```

### Note Card

**Design:**
- Glass card with subtle border
- 16px padding
- Typography hierarchy (title medium, body normal, metadata small)
- No shadow on hover, just border color change
- Verified badge (minimal, not colorful)

```tsx
<div className="glass-card p-6 group cursor-pointer
                transition-all duration-200
                hover:border-zinc-300">
  {/* Header */}
  <div className="flex items-start justify-between mb-4">
    <div>
      <h3 className="text-xl font-medium text-zinc-900 mb-1">
        French Revolution Causes
      </h3>
      <div className="flex items-center gap-3 text-sm text-zinc-500">
        <span>Sarah Kim</span>
        <span>•</span>
        <span>2 hours ago</span>
      </div>
    </div>
    
    {/* Verified badge - minimal */}
    <div className="flex items-center gap-1.5 text-xs text-zinc-600">
      <CheckCircle className="w-3.5 h-3.5" />
      <span>Verified</span>
    </div>
  </div>
  
  {/* Content preview */}
  <p className="text-base text-zinc-600 line-clamp-3 leading-relaxed">
    The French Revolution had three primary causes: economic crisis 
    following years of war, extreme social inequality between estates, 
    and the spread of Enlightenment ideas challenging divine right...
  </p>
</div>
```

### AI Chat Interface

**Design:**
- Right sidebar, frosted glass
- Messages float in, subtle scale animation
- User messages aligned right, minimal bg (zinc-100)
- AI messages aligned left, no bg (just text)
- Input at bottom, glass effect

```tsx
<aside className="glass-panel w-96 h-full flex flex-col">
  {/* Header */}
  <div className="px-6 py-5 border-b border-zinc-200">
    <h2 className="text-lg font-medium text-zinc-900">Study Assistant</h2>
    <p className="text-sm text-zinc-500 mt-1">Ask anything about this topic</p>
  </div>
  
  {/* Messages */}
  <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
    {/* AI message */}
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-zinc-900 flex-shrink-0" />
      <div className="flex-1">
        <p className="text-base text-zinc-700 leading-relaxed">
          The French Revolution began in 1789. The main causes were...
        </p>
        <div className="flex gap-2 mt-3">
          <button className="text-xs text-zinc-500 hover:text-zinc-700">
            Source: Lecture 3 Notes
          </button>
        </div>
      </div>
    </div>
    
    {/* User message */}
    <div className="flex gap-3 justify-end">
      <div className="bg-zinc-100 px-4 py-3 rounded-2xl max-w-xs">
        <p className="text-base text-zinc-900">
          What caused the French Revolution?
        </p>
      </div>
    </div>
  </div>
  
  {/* Input */}
  <div className="px-6 py-5 border-t border-zinc-200">
    <div className="flex gap-3">
      <input 
        type="text"
        placeholder="Ask a question..."
        className="flex-1 px-4 py-2.5 bg-zinc-100 border-0 rounded-lg
                   text-base text-zinc-900 placeholder:text-zinc-400
                   focus:outline-none focus:ring-2 focus:ring-zinc-900"
      />
      <button className="p-2.5 bg-zinc-900 text-white rounded-lg
                         hover:bg-zinc-800 transition-colors">
        <Send className="w-5 h-5" />
      </button>
    </div>
  </div>
</aside>
```

### Button Hierarchy

```tsx
{/* Primary - Black, used sparingly */}
<button className="px-6 py-2.5 bg-zinc-900 text-white rounded-lg
                   text-sm font-medium
                   hover:bg-zinc-800 transition-colors">
  Start Studying
</button>

{/* Secondary - Outlined */}
<button className="px-6 py-2.5 border border-zinc-300 text-zinc-700 rounded-lg
                   text-sm font-medium
                   hover:bg-zinc-50 transition-colors">
  Upload Notes
</button>

{/* Tertiary - Ghost */}
<button className="px-4 py-2 text-zinc-600 rounded-lg
                   text-sm font-medium
                   hover:bg-zinc-100 transition-colors">
  Cancel
</button>

{/* Icon-only */}
<button className="p-2 text-zinc-500 rounded-lg
                   hover:bg-zinc-100 hover:text-zinc-700 transition-all">
  <MoreHorizontal className="w-5 h-5" />
</button>
```

---

## 🏗️ Layout Patterns

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│  Navigation (Glass, 64px height)                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Page Header (96px top margin)                   │  │
│  │  - Large title (3xl)                             │  │
│  │  - Subtitle (sm, tertiary)                       │  │
│  │  - Action button (top-right)                     │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Content Grid (48px spacing)                     │  │
│  │  - Glass cards                                   │  │
│  │  - Consistent padding (24px)                     │  │
│  │  - White space between (24px gaps)               │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  80px bottom margin                                     │
└─────────────────────────────────────────────────────────┘
```

### Study View (Three Column)

```
┌───────────────────────────────────────────────────────────────┐
│  Navigation (Glass)                                           │
├────────┬──────────────────────────────────┬───────────────────┤
│        │                                  │                   │
│ Aside  │  Main Content                    │  AI Chat          │
│ 320px  │  Flex-1                          │  384px            │
│        │                                  │                   │
│ Pre-   │  ┌────────────────────────────┐ │  ┌─────────────┐ │
│ Class  │  │  Topic Header              │ │  │  Messages   │ │
│ Info   │  │  - Title                   │ │  │             │ │
│        │  │  - Study button            │ │  │             │ │
│ Glass  │  └────────────────────────────┘ │  │             │ │
│ Panel  │                                  │  │             │ │
│        │  ┌────────────────────────────┐ │  │             │ │
│        │  │  Note Card                 │ │  │             │ │
│        │  │  Glass, minimal            │ │  │             │ │
│        │  └────────────────────────────┘ │  │             │ │
│        │                                  │  │             │ │
│        │  ┌────────────────────────────┐ │  │             │ │
│        │  │  Note Card                 │ │  │             │ │
│        │  └────────────────────────────┘ │  └─────────────┘ │
│        │                                  │  Input (Glass)  │
│        │  48px spacing between cards      │                   │
└────────┴──────────────────────────────────┴───────────────────┘
```

---

## ✨ Micro-Interactions

### Hover States

```css
/* Cards */
.card {
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
}
.card:hover {
  border-color: #D6D3D1; /* Subtle */
  transform: translateY(-1px); /* Barely noticeable lift */
}

/* Buttons */
.button {
  transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
}
.button:hover {
  transform: translateY(-1px);
}
.button:active {
  transform: translateY(0);
}

/* Links */
.link {
  transition: color 150ms ease;
}
.link:hover {
  color: #18181B; /* Darker on hover */
}
```

### Loading States

```tsx
{/* Skeleton - subtle, not shimmer */}
<div className="animate-pulse">
  <div className="h-4 bg-zinc-200 rounded w-3/4 mb-3" />
  <div className="h-4 bg-zinc-200 rounded w-1/2" />
</div>

{/* Spinner - minimal */}
<div className="w-5 h-5 border-2 border-zinc-300 border-t-zinc-900 
                rounded-full animate-spin" />
```

### Page Transitions

```tsx
// Framer Motion variants
const pageVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 }
};

const pageTransition = {
  type: "tween",
  ease: "easeInOut",
  duration: 0.2
};
```

---

## 🎯 Component Inventory

### Core Components (Build First)

1. **GlassCard** - Base for all content containers
2. **NavigationBar** - Fixed glass nav
3. **SidebarPanel** - Floating glass sidebars
4. **MessageBubble** - AI chat messages
5. **NoteCard** - Note display with metadata
6. **Button** (Primary, Secondary, Tertiary, Icon)
7. **Input** - Text inputs with focus states
8. **Badge** - Minimal status indicators

### Layout Components

9. **PageHeader** - Consistent page titles
10. **ContentGrid** - Responsive grid for cards
11. **ThreeColumnLayout** - Study view layout
12. **EmptyState** - Centered, minimal empty states

### Advanced Components

13. **VoiceRecorder** - Waveform visualization
14. **ProgressRing** - Circular progress (minimal)
15. **Dropdown** - Minimal menu
16. **Modal** - Glass overlay modal
17. **Toast** - Bottom-right notifications

---

## 📱 Responsive Breakpoints

```css
--breakpoint-sm: 640px;   /* Mobile */
--breakpoint-md: 768px;   /* Tablet */
--breakpoint-lg: 1024px;  /* Laptop */
--breakpoint-xl: 1280px;  /* Desktop */
--breakpoint-2xl: 1536px; /* Wide */
```

### Mobile Adaptations

1. **Navigation** - Hamburger menu, glass sheet from left
2. **Three-column → Stack** - Sidebar becomes modal
3. **Glass effects** - Reduce blur on mobile (performance)
4. **Touch targets** - Minimum 44px height
5. **Bottom nav** - Replace top nav on mobile

---

## 🎨 Background Patterns (Subtle)

### Option 1: Noise Texture

```css
.page-background {
  background-color: #FAFAF9;
  background-image: url('data:image/svg+xml,...'); /* Subtle noise */
  background-size: 200px 200px;
}
```

### Option 2: Gradient Mesh (Very Subtle)

```css
.page-background {
  background: 
    radial-gradient(at 0% 0%, rgba(250, 250, 249, 0.8) 0px, transparent 50%),
    radial-gradient(at 100% 100%, rgba(245, 245, 244, 0.8) 0px, transparent 50%),
    #FAFAF9;
}
```

### Option 3: Grid Lines (Developer Aesthetic)

```css
.page-background {
  background-color: #FAFAF9;
  background-image: 
    linear-gradient(rgba(0, 0, 0, 0.02) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 0, 0, 0.02) 1px, transparent 1px);
  background-size: 32px 32px; /* Aligned to grid */
}
```

---

## 🚫 What NOT to Do

### Typography
- ❌ Comic Sans, Papyrus, or any "fun" fonts
- ❌ More than 2 font families
- ❌ Centered text for body content
- ❌ ALL CAPS for anything longer than labels

### Colors
- ❌ Rainbow palettes
- ❌ Bright, saturated colors
- ❌ Gradients (except very subtle background)
- ❌ More than 1 accent color

### Layout
- ❌ Inconsistent spacing
- ❌ Centered content without max-width
- ❌ Cards with heavy shadows
- ❌ Cluttered, dense layouts

### Components
- ❌ Emoji as UI elements (💬 Send)
- ❌ Colorful icons
- ❌ Excessive animations
- ❌ Confetti, sparkles, or particle effects

---

## 📋 Design Checklist

Before shipping any component:

**Visual**
- [ ] Uses neutral color palette (90%+ grays)
- [ ] Follows 8px spacing grid
- [ ] Typography scale is consistent
- [ ] Glass effect is subtle, not overdone
- [ ] No gradients except background (if any)

**Interaction**
- [ ] Hover states are subtle
- [ ] Transitions are fast (<200ms)
- [ ] Loading states are minimal
- [ ] Focus states are visible (accessibility)

**Layout**
- [ ] Aligned to grid
- [ ] Proper hierarchy (size, weight, color)
- [ ] Sufficient white space
- [ ] Responsive at all breakpoints

**Code**
- [ ] Tailwind classes follow order (layout → spacing → colors → effects)
- [ ] No hardcoded values (use design tokens)
- [ ] Accessible (ARIA labels, keyboard nav)
- [ ] Semantic HTML

---

## 🎬 Example: Complete Study View

```tsx
export default function StudyView() {
  return (
    <div className="min-h-screen bg-[#FAFAF9]">
      {/* Navigation */}
      <nav className="fixed top-0 w-full h-16 px-20
                      bg-[rgba(250,250,249,0.72)] backdrop-blur-[40px]
                      border-b border-black/5 z-50">
        <div className="flex items-center justify-between h-full">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-zinc-900 rounded-lg" />
            <span className="text-lg font-medium text-zinc-900">NotesOS</span>
          </div>
          <div className="text-sm text-zinc-600">HIST 101</div>
          <div className="w-9 h-9 rounded-full bg-zinc-200" />
        </div>
      </nav>

      {/* Main Layout */}
      <div className="flex pt-16 h-screen">
        {/* Left Sidebar - Pre-Class Research */}
        <aside className="w-80 border-r border-zinc-200 overflow-y-auto">
          <div className="p-8">
            <div className="mb-6">
              <h3 className="text-sm font-medium text-zinc-900 mb-2">
                Before Class
              </h3>
              <p className="text-sm text-zinc-500">
                AI-generated overview
              </p>
            </div>
            
            <div className="space-y-4">
              <div>
                <h4 className="text-xs font-medium text-zinc-900 mb-2">
                  Key Concepts
                </h4>
                <ul className="space-y-2 text-sm text-zinc-600">
                  <li>• Ancien Régime</li>
                  <li>• Estates-General</li>
                  <li>• Tennis Court Oath</li>
                </ul>
              </div>
            </div>
          </div>
        </aside>

        {/* Center - Notes */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto px-12 py-12">
            {/* Header */}
            <div className="mb-12">
              <h1 className="text-4xl font-semibold text-zinc-900 mb-3">
                French Revolution
              </h1>
              <p className="text-base text-zinc-500">
                Week 3 • 12 notes shared
              </p>
            </div>

            {/* Notes */}
            <div className="space-y-6">
              <div className="bg-white/70 backdrop-blur-[20px]
                            border border-white/20 rounded-xl p-6
                            hover:border-zinc-300 transition-all duration-200
                            shadow-[0_8px_32px_0_rgba(31,38,135,0.07)]">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-xl font-medium text-zinc-900 mb-1">
                      Lecture 3 Notes
                    </h3>
                    <div className="flex items-center gap-3 text-sm text-zinc-500">
                      <span>Sarah Kim</span>
                      <span>•</span>
                      <span>2 hours ago</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-zinc-600">
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" />
                    </svg>
                    <span>Verified</span>
                  </div>
                </div>
                <p className="text-base text-zinc-600 leading-relaxed">
                  The French Revolution had three primary causes: economic crisis 
                  following years of war, extreme social inequality between estates, 
                  and the spread of Enlightenment ideas...
                </p>
              </div>
            </div>
          </div>
        </main>

        {/* Right Sidebar - AI Chat */}
        <aside className="w-96 border-l border-zinc-200 flex flex-col
                        bg-white/85 backdrop-blur-[30px]">
          <div className="px-6 py-5 border-b border-zinc-200">
            <h2 className="text-lg font-medium text-zinc-900">Study Assistant</h2>
            <p className="text-sm text-zinc-500 mt-1">Ask anything</p>
          </div>
          
          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
            {/* Messages here */}
          </div>
          
          <div className="px-6 py-5 border-t border-zinc-200">
            <input 
              type="text"
              placeholder="Ask a question..."
              className="w-full px-4 py-2.5 bg-zinc-100 rounded-lg
                       text-base text-zinc-900 placeholder:text-zinc-400
                       border-0 focus:outline-none focus:ring-2 focus:ring-zinc-900"
            />
          </div>
        </aside>
      </div>
    </div>
  );
}
```

---

## Document End

**Design Principles to Remember:**

1. **Neutral first** - Let content be the color
2. **Glass, not gradients** - Depth through transparency
3. **Intentional spacing** - Every pixel aligned to 8px grid
4. **Minimal motion** - Subtle, purposeful animations
5. **Typography hierarchy** - Size + weight + color, not decoration

**This is Apple-level polish. Every detail matters.** ✨