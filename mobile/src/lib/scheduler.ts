/**
 * Spaced-repetition rules — a port of cards/scheduler.py on the server.
 *
 * - A correct answer adds one to the card's count on its stage; at
 *   REQUIRED_CORRECT[stage] the card moves up and the count restarts.
 *   Next review = interval of the stage the card is on after the answer.
 * - A wrong answer changes nothing and makes the card due right away.
 * - The last stage is sticky.
 *
 * Both sides are tested against cards/scheduler_vectors.json; keep them in step.
 */

export const STAGE_INTERVALS_S = [90, 1800, 43200, 172800, 604800, 1209600, 2592000];
export const REQUIRED_CORRECT = [3, 3, 3, 2, 2, 2];
export const MAX_STAGE = STAGE_INTERVALS_S.length - 1;

export type CardState = { stage: number; correctCount: number };

export function nextState(stage: number, correctCount: number, correct: boolean): CardState {
  if (!correct) return { stage, correctCount };
  if (stage >= MAX_STAGE) return { stage: MAX_STAGE, correctCount: 0 };
  const count = correctCount + 1;
  if (count >= REQUIRED_CORRECT[stage]) return { stage: stage + 1, correctCount: 0 };
  return { stage, correctCount: count };
}

/** Apply one answer at `nowMs`. Returns the new state and the next review time (ms). */
export function scheduleNextReview(
  stage: number,
  correctCount: number,
  correct: boolean,
  nowMs: number,
): CardState & { nextReviewAt: number } {
  const next = nextState(stage, correctCount, correct);
  const wait = correct ? STAGE_INTERVALS_S[next.stage] * 1000 : 0;
  return { ...next, nextReviewAt: nowMs + wait };
}
