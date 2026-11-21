/**
 * LaTeX in card text. Formulas are written as $$…$$ or \[…\] (on their own
 * line) and \(…\) (inline). A single $ is plain text, so shell cards such
 * as "$HOME" are left alone — same rules as the website (static/web/app.js).
 */
import katex from 'katex';

export type Segment = { text: string } | { tex: string; display: boolean };

const PATTERN = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)/g;

export function hasMath(text: string): boolean {
  PATTERN.lastIndex = 0;
  return PATTERN.test(text);
}

export function splitMath(text: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  PATTERN.lastIndex = 0;
  for (let m = PATTERN.exec(text); m; m = PATTERN.exec(text)) {
    if (m.index > last) out.push({ text: text.slice(last, m.index) });
    out.push(m[3] !== undefined ? { tex: m[3], display: false } : { tex: (m[1] ?? m[2]) as string, display: true });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}

const escapeHtml = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/** HTML with MathML formulas: the phone's WebView draws MathML itself, offline, without fonts. */
export function toHtml(text: string): string {
  return splitMath(text)
    .map((s) =>
      'text' in s
        ? escapeHtml(s.text)
        : katex.renderToString(s.tex, { output: 'mathml', displayMode: s.display, throwOnError: false }),
    )
    .join('');
}

// ------------------------------------------------ readable text for lists

const SYMBOLS: Record<string, string> = {
  alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', Delta: 'Δ', epsilon: 'ε', varepsilon: 'ε', eta: 'η', theta: 'θ',
  vartheta: 'ϑ', lambda: 'λ', mu: 'μ', pi: 'π', rho: 'ρ', sigma: 'σ', Sigma: 'Σ', tau: 'τ', varphi: 'φ', phi: 'φ',
  Phi: 'Φ', omega: 'ω', Omega: 'Ω', Theta: 'Θ', kappa: 'κ', cdot: '·', times: '×', parallel: '∥', infty: '∞',
  approx: '≈', le: '≤', leq: '≤', ge: '≥', geq: '≥', ne: '≠', neq: '≠', pm: '±', to: '→', rightarrow: '→',
  Rightarrow: '⇒', sum: 'Σ', int: '∫', partial: '∂', circ: '°', quad: ' ', qquad: '  ', ll: '≪', gg: '≫', sim: '~',
};
const SUP: Record<string, string> = { '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '-': '⁻', '+': '⁺', n: 'ⁿ' };
const SUB: Record<string, string> = { '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉', '-': '₋', '+': '₊' };

function scripts(s: string, table: Record<string, string>, mark: string): string {
  const conv = (v: string) => ([...v].every((ch) => table[ch]) ? [...v].map((ch) => table[ch]).join('') : `${mark}(${v})`);
  return s
    .replace(new RegExp(`\\${mark}\\{([^{}]*)\\}`, 'g'), (_, v) => conv(v))
    .replace(new RegExp(`\\${mark}([A-Za-z0-9+-])`, 'g'), (_, v) => (table[v] ?? `${mark}${v}`));
}

/** Rough plain-text version of a formula, e.g. "\frac{U}{I}" → "U/I", "I^2 R" → "I² R". */
export function texToPlain(tex: string): string {
  let s = tex;
  for (let i = 0; i < 4; i++) {
    s = s
      .replace(/\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}/g, (_, a, b) => `${a.length > 1 ? `(${a})` : a}/${b.length > 1 ? `(${b})` : b}`)
      .replace(/\\sqrt\{([^{}]*)\}/g, '√($1)')
      .replace(/\\(?:text|mathrm|mathbf|operatorname)\{([^{}]*)\}/g, '$1');
  }
  s = s.replace(/\\([A-Za-z]+)/g, (m, name) => SYMBOLS[name] ?? m).replace(/\\[,;! ]/g, ' ');
  s = scripts(s, SUP, '^');
  s = scripts(s, SUB, '_');
  return s.replace(/[{}]/g, '').replace(/\s+/g, ' ').trim();
}

export function mathToPlain(text: string): string {
  if (!hasMath(text)) return text;
  return splitMath(text).map((s) => ('text' in s ? s.text : texToPlain(s.tex))).join('');
}
