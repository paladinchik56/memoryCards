/**
 * Local SQLite database: the user's blitz lives here so studying works offline.
 * `outbox` queues changes until the next sync (see sync.ts).
 */
import type { SQLiteDatabase } from 'expo-sqlite';
import * as Crypto from 'expo-crypto';

import { scheduleNextReview } from './scheduler';

export const DB_NAME = 'cards.db';
const SCHEMA_VERSION = 1;

export async function migrate(db: SQLiteDatabase) {
  const row = await db.getFirstAsync<{ user_version: number }>('PRAGMA user_version');
  let version = row?.user_version ?? 0;
  if (version >= SCHEMA_VERSION) return;
  if (version === 0) {
    await db.execAsync(`
      PRAGMA journal_mode = WAL;
      CREATE TABLE collections (
        uuid TEXT PRIMARY KEY NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        visibility TEXT NOT NULL DEFAULT 'private',
        updated_at TEXT NOT NULL
      );
      CREATE TABLE cards (
        uuid TEXT PRIMARY KEY NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        collection TEXT,
        stage INTEGER NOT NULL DEFAULT 0,
        correct_count INTEGER NOT NULL DEFAULT 0,
        is_reviewed INTEGER NOT NULL DEFAULT 0,
        next_review_at INTEGER NOT NULL,
        content_updated_at TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
      CREATE INDEX cards_due ON cards (next_review_at);
      CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, payload TEXT NOT NULL);
      CREATE TABLE meta (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL);
      CREATE TABLE study_days (day TEXT PRIMARY KEY NOT NULL);
    `);
    version = 1;
  }
  await db.execAsync(`PRAGMA user_version = ${version}`);
}

// ------------------------------------------------------------------ types

export type Card = {
  uuid: string;
  question: string;
  answer: string;
  collection: string | null;
  stage: number;
  correct_count: number;
  is_reviewed: number;
  next_review_at: number; // ms
  content_updated_at: string;
  created_at: string;
};

export type Collection = { uuid: string; name: string; description: string; visibility: string; updated_at: string };

export type TopicFilter = { topics: string[]; noTopic: boolean } | null; // null = all

// ------------------------------------------------------------------- meta

export async function getMeta(db: SQLiteDatabase, key: string): Promise<string | null> {
  const row = await db.getFirstAsync<{ value: string }>('SELECT value FROM meta WHERE key = ?', key);
  return row?.value ?? null;
}

export async function setMeta(db: SQLiteDatabase, key: string, value: string | null) {
  if (value === null) await db.runAsync('DELETE FROM meta WHERE key = ?', key);
  else await db.runAsync('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', key, value);
}

export async function wipe(db: SQLiteDatabase) {
  await db.execAsync('DELETE FROM cards; DELETE FROM collections; DELETE FROM outbox; DELETE FROM meta; DELETE FROM study_days;');
}

// ----------------------------------------------------------------- queries

function filterSql(filter: TopicFilter): { sql: string; params: string[] } {
  if (!filter) return { sql: '', params: [] };
  const parts: string[] = [];
  if (filter.topics.length) parts.push(`collection IN (${filter.topics.map(() => '?').join(',')})`);
  if (filter.noTopic) parts.push('collection IS NULL');
  if (!parts.length) return { sql: ' AND 0', params: [] };
  return { sql: ` AND (${parts.join(' OR ')})`, params: filter.topics };
}

export async function dueCards(db: SQLiteDatabase, nowMs: number, filter: TopicFilter = null): Promise<Card[]> {
  const f = filterSql(filter);
  return db.getAllAsync<Card>(`SELECT * FROM cards WHERE next_review_at <= ?${f.sql}`, nowMs, ...f.params);
}

export async function countDue(db: SQLiteDatabase, nowMs: number, filter: TopicFilter = null): Promise<number> {
  const f = filterSql(filter);
  const row = await db.getFirstAsync<{ n: number }>(`SELECT COUNT(*) AS n FROM cards WHERE next_review_at <= ?${f.sql}`, nowMs, ...f.params);
  return row?.n ?? 0;
}

export async function stats(db: SQLiteDatabase, maxStage: number) {
  const row = await db.getFirstAsync<{ total: number; learned: number }>(
    'SELECT COUNT(*) AS total, COALESCE(SUM(stage >= ?), 0) AS learned FROM cards', maxStage,
  );
  const days = await db.getAllAsync<{ day: string }>('SELECT day FROM study_days ORDER BY day DESC LIMIT 400');
  return { total: row?.total ?? 0, learned: row?.learned ?? 0, streak: streak(days.map((d) => d.day)) };
}

const dayKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

/** Consecutive study days ending today (or yesterday, if not studied yet today). */
function streak(daysDesc: string[]): number {
  const set = new Set(daysDesc);
  const d = new Date();
  if (!set.has(dayKey(d))) d.setDate(d.getDate() - 1);
  let n = 0;
  while (set.has(dayKey(d))) {
    n++;
    d.setDate(d.getDate() - 1);
  }
  return n;
}

export async function allCards(db: SQLiteDatabase): Promise<(Card & { topic: string | null })[]> {
  return db.getAllAsync(
    `SELECT cards.*, collections.name AS topic FROM cards
     LEFT JOIN collections ON collections.uuid = cards.collection
     ORDER BY next_review_at`,
  );
}

export async function topicCards(db: SQLiteDatabase, collection: string | null): Promise<Card[]> {
  return collection
    ? db.getAllAsync<Card>('SELECT * FROM cards WHERE collection = ? ORDER BY created_at', collection)
    : db.getAllAsync<Card>('SELECT * FROM cards WHERE collection IS NULL ORDER BY created_at');
}

export async function collections(db: SQLiteDatabase): Promise<(Collection & { count: number })[]> {
  return db.getAllAsync(
    `SELECT collections.*, (SELECT COUNT(*) FROM cards WHERE cards.collection = collections.uuid) AS count
     FROM collections ORDER BY name COLLATE NOCASE`,
  );
}

export async function noTopicCount(db: SQLiteDatabase): Promise<number> {
  const row = await db.getFirstAsync<{ n: number }>('SELECT COUNT(*) AS n FROM cards WHERE collection IS NULL');
  return row?.n ?? 0;
}

// ----------------------------------------------------------------- writes

async function enqueue(db: SQLiteDatabase, kind: string, payload: object) {
  await db.runAsync('INSERT INTO outbox (kind, payload) VALUES (?, ?)', kind, JSON.stringify(payload));
}

/** Grade a card locally and queue the review event for the server. */
export async function answer(db: SQLiteDatabase, card: Card, correct: boolean, nowMs = Date.now()) {
  const next = scheduleNextReview(card.stage, card.correct_count, correct, nowMs);
  await db.withTransactionAsync(async () => {
    await db.runAsync(
      'UPDATE cards SET stage = ?, correct_count = ?, next_review_at = ?, is_reviewed = 1 WHERE uuid = ?',
      next.stage, next.correctCount, next.nextReviewAt, card.uuid,
    );
    await enqueue(db, 'review', {
      uuid: Crypto.randomUUID(), card: card.uuid, correct, reviewed_at: new Date(nowMs).toISOString(),
    });
    await db.runAsync('INSERT OR IGNORE INTO study_days (day) VALUES (?)', dayKey(new Date(nowMs)));
  });
}

export class DuplicateQuestion extends Error {}

/** Add a new own card (it goes straight into the blitz). */
export async function addCard(db: SQLiteDatabase, question: string, answerText: string, collection: string | null) {
  question = question.trim();
  answerText = answerText.trim();
  const dup = await db.getFirstAsync('SELECT uuid FROM cards WHERE question = ?', question);
  if (dup) throw new DuplicateQuestion();
  const now = new Date();
  const card = {
    uuid: Crypto.randomUUID(), question, answer: answerText, collection,
    content_updated_at: now.toISOString(), created_at: now.toISOString(),
  };
  await db.withTransactionAsync(async () => {
    await db.runAsync(
      `INSERT INTO cards (uuid, question, answer, collection, next_review_at, content_updated_at, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      card.uuid, question, answerText, collection, now.getTime(), card.content_updated_at, card.created_at,
    );
    await enqueue(db, 'card', {
      uuid: card.uuid, question, answer: answerText, collection, content_updated_at: card.content_updated_at,
    });
  });
}
