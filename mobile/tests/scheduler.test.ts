// Run with `npm test` (Node's built-in test runner; Node strips the TS types).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { REQUIRED_CORRECT, STAGE_INTERVALS_S, scheduleNextReview } from '../src/lib/scheduler';
import { afterAnswer, chooseNext, newState } from '../src/lib/blitz';

const vectors = JSON.parse(readFileSync(new URL('../../cards/scheduler_vectors.json', import.meta.url), 'utf8'));

test('scheduler matches the shared server vectors', () => {
  assert.deepEqual(STAGE_INTERVALS_S, vectors.intervals_seconds);
  assert.deepEqual(REQUIRED_CORRECT, vectors.required_correct);
  const now = 1_700_000_000_000;
  for (const c of vectors.cases) {
    const r = scheduleNextReview(c.stage, c.correct_count, c.correct, now);
    assert.deepEqual([r.stage, r.correctCount, (r.nextReviewAt - now) / 1000], [c.new_stage, c.new_correct_count, c.wait_seconds], JSON.stringify(c));
  }
});

let seed = 1;
const rng = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
const cards = (n: number) => Array.from({ length: n }, (_, i) => ({ uuid: `c${i}`, stage: 0, next_review_at: Date.now() }));

test('wrong card comes back after 5-6 others', () => {
  const due = cards(20);
  let state = afterAnswer(newState(), 'c0', false, rng);
  let gap = 0;
  for (;;) {
    const card = chooseNext(due, Date.now(), state, rng)!;
    if (card.uuid === 'c0') break;
    gap++;
    state = afterAnswer(state, card.uuid, true, rng);
  }
  assert.ok(gap === 5 || gap === 6, `gap ${gap}`);
});

test('never the same card twice in a row; overdue first', () => {
  const due = cards(2);
  assert.equal(chooseNext(due, Date.now(), afterAnswer(newState(), 'c0', true))!.uuid, 'c1');
  const now = Date.now();
  const mixed = [
    ...Array.from({ length: 10 }, (_, i) => ({ uuid: `m${i}`, stage: 6, next_review_at: now - 3600_000 })),
    { uuid: 'late', stage: 1, next_review_at: now - 3600_000 },
  ];
  for (let i = 0; i < 20; i++) assert.equal(chooseNext(mixed, now, newState(), rng)!.uuid, 'late');
});

import { hasMath, mathToPlain, splitMath, texToPlain } from '../src/lib/math';

test('LaTeX: delimiters, and a single $ stays plain text', () => {
  assert.equal(hasMath('echo $HOME $(date) $((3+5))'), false);
  assert.equal(hasMath('R = \\(\\frac{U}{I}\\)'), true);
  assert.deepEqual(splitMath('a $$x^2$$ b'), [{ text: 'a ' }, { tex: 'x^2', display: true }, { text: ' b' }]);
  assert.equal(texToPlain('\\frac{U}{I}'), 'U/I');
  assert.equal(texToPlain('P = I^2 R_{12}'), 'P = I² R₁₂');
  assert.equal(texToPlain('\\varepsilon_0 \\cdot \\frac{A}{l}'), 'ε₀ · A/l');
  assert.equal(mathToPlain('Ohm: \\(R = \\frac{U}{I}\\)'), 'Ohm: R = U/I');
});
