// LaTeX handling for the note body. Display math ($$…$$, \[…\]) is split out and rendered
// as real MathJax SVG (MathBlock). Inline math ($…$, \(…\)) is converted to Unicode so it
// flows inside the prose as tappable text — an SVG View can't sit mid-line inside a wrapping
// RN <Text>, so inline stays text. Full inline TeX (fractions, integrals) degrades to a
// readable approximation; display math keeps full fidelity.

export interface NoteSegment {
  type: 'md' | 'math';
  content: string;
}

const DISPLAY_MATH = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]/g;
const INLINE_MATH = /\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)/g;

/** Split the note into markdown runs and display-math blocks (block-level, so splitting
 *  never breaks a paragraph). Inline math is left in the markdown runs for convertInlineMath. */
export function splitNoteSegments(md: string): NoteSegment[] {
  const segments: NoteSegment[] = [];
  let last = 0;
  DISPLAY_MATH.lastIndex = 0;
  for (const match of md.matchAll(DISPLAY_MATH)) {
    if (match.index === undefined) continue;
    if (match.index > last) segments.push({ type: 'md', content: md.slice(last, match.index) });
    segments.push({ type: 'math', content: (match[1] ?? match[2] ?? '').trim() });
    last = match.index + match[0].length;
  }
  if (last < md.length) segments.push({ type: 'md', content: md.slice(last) });
  return segments.filter((s) => s.type === 'math' || s.content.trim().length > 0);
}

const COMMANDS: Record<string, string> = {
  // Greek (lower)
  alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', epsilon: 'ε', varepsilon: 'ε', zeta: 'ζ',
  eta: 'η', theta: 'θ', vartheta: 'ϑ', iota: 'ι', kappa: 'κ', lambda: 'λ', mu: 'μ', nu: 'ν',
  xi: 'ξ', omicron: 'ο', pi: 'π', rho: 'ρ', sigma: 'σ', tau: 'τ', upsilon: 'υ', phi: 'φ',
  varphi: 'φ', chi: 'χ', psi: 'ψ', omega: 'ω',
  // Greek (upper)
  Gamma: 'Γ', Delta: 'Δ', Theta: 'Θ', Lambda: 'Λ', Xi: 'Ξ', Pi: 'Π', Sigma: 'Σ',
  Upsilon: 'Υ', Phi: 'Φ', Psi: 'Ψ', Omega: 'Ω',
  // Operators / relations / symbols
  times: '×', cdot: '⋅', div: '÷', pm: '±', mp: '∓', ast: '∗', star: '⋆',
  leq: '≤', le: '≤', geq: '≥', ge: '≥', neq: '≠', ne: '≠', approx: '≈', equiv: '≡',
  sim: '∼', simeq: '≃', cong: '≅', propto: '∝', ll: '≪', gg: '≫',
  to: '→', rightarrow: '→', leftarrow: '←', leftrightarrow: '↔', Rightarrow: '⇒',
  Leftarrow: '⇐', Leftrightarrow: '⇔', mapsto: '↦', uparrow: '↑', downarrow: '↓',
  infty: '∞', partial: '∂', nabla: '∇', sum: '∑', prod: '∏', int: '∫', oint: '∮',
  in: '∈', notin: '∉', ni: '∋', subset: '⊂', subseteq: '⊆', supset: '⊃', supseteq: '⊇',
  cup: '∪', cap: '∩', emptyset: '∅', varnothing: '∅', forall: '∀', exists: '∃',
  neg: '¬', land: '∧', lor: '∨', wedge: '∧', vee: '∨', oplus: '⊕', otimes: '⊗',
  angle: '∠', perp: '⊥', parallel: '∥', cdots: '⋯', ldots: '…', dots: '…', vdots: '⋮',
  prime: '′', circ: '∘', bullet: '•', degree: '°', deg: '°', hbar: 'ℏ', ell: 'ℓ',
  Re: 'ℜ', Im: 'ℑ', aleph: 'ℵ', surd: '√', therefore: '∴', because: '∵',
};

const SUP: Record<string, string> = {
  '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸',
  '9': '⁹', '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾', n: 'ⁿ', i: 'ⁱ',
};
const SUB: Record<string, string> = {
  '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈',
  '9': '₉', '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎', a: 'ₐ', e: 'ₑ', o: 'ₒ',
  x: 'ₓ', h: 'ₕ', k: 'ₖ', l: 'ₗ', m: 'ₘ', n: 'ₙ', p: 'ₚ', s: 'ₛ', t: 'ₜ',
};

// Trailing \s? swallows the TeX command terminator space so "\Delta G" → "ΔG", not "Δ G".
const CMD_REGEX = new RegExp(
  '\\\\(' + Object.keys(COMMANDS).sort((a, b) => b.length - a.length).join('|') + ')(?![a-zA-Z])\\s?',
  'g'
);

function toScript(s: string, map: Record<string, string>): string | null {
  const chars = [...s].map((ch) => map[ch]);
  return chars.every(Boolean) ? chars.join('') : null;
}

/** Best-effort TeX → Unicode for inline math (see file header). */
export function texToUnicode(tex: string): string {
  let s = tex;
  s = s.replace(/\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, '($1)/($2)');
  s = s.replace(/\\sqrt\s*\{([^{}]*)\}/g, '√($1)');
  s = s.replace(/\\(?:text|mathrm|mathbf|mathit|operatorname)\s*\{([^{}]*)\}/g, '$1');
  s = s.replace(CMD_REGEX, (_m, name) => COMMANDS[name]);
  s = s.replace(/\^\{([^{}]*)\}|\^(\S)/g, (_m, braced, one) => {
    const t = braced ?? one;
    return toScript(t, SUP) ?? `^(${t})`;
  });
  s = s.replace(/_\{([^{}]*)\}|_(\S)/g, (_m, braced, one) => {
    const t = braced ?? one;
    return toScript(t, SUB) ?? `_${t}`;
  });
  s = s.replace(/\\left|\\right|\\!|\\,|\\;|\\:|\\quad|\\qquad/g, '');
  s = s.replace(/\\[a-zA-Z]+/g, (m) => m.slice(1));
  s = s.replace(/[{}]/g, '');
  return s.trim();
}

/** Replace inline math in a markdown run with its Unicode approximation. */
export function convertInlineMath(md: string): string {
  return md.replace(INLINE_MATH, (_full, dollar, paren) => texToUnicode(dollar ?? paren ?? ''));
}
