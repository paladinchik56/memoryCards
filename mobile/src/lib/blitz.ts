/**
 * Which card the blitz shows next — a port of cards/blitz.py.
 *
 * Random order, but cards overdue by at least one full interval of their
 * stage go first. The same card never comes twice in a row. A card answered
 * wrong is held back for 5-6 other cards, then shown first; with fewer cards
 * left it comes back right after them.
 */
import { STAGE_INTERVALS_S } from './scheduler';

export const COMEBACK_MIN = 5;
export const COMEBACK_MAX = 6;
const OVERDUE_RATIO = 1;

export type BlitzCard = { uuid: string; stage: number; next_review_at: number };
export type BlitzState = { last: string | null; held: Record<string, number> };
export type Rng = () => number; // like Math.random

export const newState = (): BlitzState => ({ last: null, held: {} });

const pick = <T,>(items: T[], rng: Rng): T => items[Math.floor(rng() * items.length)];

export function overdueRatio(card: BlitzCard, nowMs: number): number {
  const interval = STAGE_INTERVALS_S[Math.min(card.stage, STAGE_INTERVALS_S.length - 1)] * 1000;
  return (nowMs - card.next_review_at) / interval;
}

export function chooseNext<T extends BlitzCard>(due: T[], nowMs: number, state: BlitzState, rng: Rng = Math.random): T | null {
  if (due.length === 0) return null;
  const { held, last } = state;

  const released = due.filter((c) => held[c.uuid] === 0 && c.uuid !== last);
  if (released.length) return pick(released, rng);

  const ready = due.filter((c) => !(c.uuid in held) && c.uuid !== last);
  if (!ready.length) {
    const waiting = due.filter((c) => c.uuid !== last).sort((a, b) => (held[a.uuid] ?? 0) - (held[b.uuid] ?? 0));
    return waiting[0] ?? due[0];
  }
  const urgent = ready.filter((c) => overdueRatio(c, nowMs) >= OVERDUE_RATIO);
  return pick(urgent.length ? urgent : ready, rng);
}

export function afterAnswer(state: BlitzState, uuid: string, correct: boolean, rng: Rng = Math.random): BlitzState {
  const held: Record<string, number> = {};
  for (const [k, v] of Object.entries(state.held)) held[k] = k !== uuid && v > 0 ? v - 1 : v;
  if (correct) delete held[uuid];
  else held[uuid] = COMEBACK_MIN + Math.floor(rng() * (COMEBACK_MAX - COMEBACK_MIN + 1));
  return { last: uuid, held };
}
