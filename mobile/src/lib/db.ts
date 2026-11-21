/**
 * Local SQLite database: the user's cards, topics, added topics and topic
 * runs live here, so studying works offline. `outbox` queues changes until
 * the next sync (see sync.ts).
 */
import type { SQLiteDatabase } from 'expo-sqlite';
import * as Crypto from 'expo-crypto';

import { scheduleNextReview } from './scheduler';

export const DB_NAME = 'cards.db';
const SCHEMA_VERSION = 2;

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
  if (version === 1) {
    await db.execAsync(`
      ALTER TABLE cards ADD COLUMN in_pool INTEGER NOT NULL DEFAULT 1;
      ALTER TABLE cards ADD COLUMN source_collection TEXT;
      ALTER TABLE collections ADD COLUMN tags TEXT NOT NULL DEFAULT '[]';
      CREATE TABLE added_topics (
        uuid TEXT PRIMARY KEY NOT NULL, share_token TEXT NOT NULL, name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]', owner TEXT NOT NULL
      );
      CREATE TABLE added_cards (
        uuid TEXT PRIMARY KEY NOT NULL, topic TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL, position INTEGER NOT NULL
      );
      CREATE TABLE topic_runs (
        collection TEXT PRIMARY KEY NOT NULL, round INTEGER NOT NULL, queue TEXT NOT NULL, wrong TEXT NOT NULL,
        round_total INTEGER NOT NULL, correct_count INTEGER NOT NULL, updated_at TEXT NOT NULL
      );
    `);
    // Version 1 never synced in_pool: download everything again on the next sync.
    await db.runAsync("DELETE FROM meta WHERE key = 'since'");
    version = 2;
  }
  await db.execAsync(`PRAGMA user_version = ${version}`);
}

// ------------------------------------------------------------------ types

export type Card = {
  uuid: string;
  question: string;
  answer: string;
  collection: string | null;
  source_collection: string | null;
  in_pool: number;
  stage: number;
  correct_count: number;
  is_reviewed: number;
  next_review_at: number; // ms
  content_updated_at: string;
  created_at: string;
};

export type Collection = {
  uuid: string; name: string; description: string; visibility: string; tags: string; updated_at: string;
};
export type AddedTopic = { uuid: string; share_token: string; name: string; description: string; tags: string; owner: string };
export type SimpleCard = { uuid: string; question: string; answer: string };

/** Blitz filter: own topics match a card's topic, added topics match where a copy came from. */
export type TopicFilter = { topics: string[]; noTopic: boolean } | null; // null = all

export const parseTags = (json: string): string[] => {
  try {
    const v = JSON.parse(json);
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
};

const now = () => new Date().toISOString();

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
  await db.execAsync(`
    DELETE FROM cards; DELETE FROM collections; DELETE FROM outbox; DELETE FROM meta; DELETE FROM study_days;
    DELETE FROM added_topics; DELETE FROM added_cards; DELETE FROM topic_runs;
  `);
}

async function enqueue(db: SQLiteDatabase, kind: string, payload: object) {
  await db.runAsync('INSERT INTO outbox (kind, payload) VALUES (?, ?)', kind, JSON.stringify(payload));
}

// ------------------------------------------------------------------ blitz

function filterSql(filter: TopicFilter): { sql: string; params: string[] } {
  if (!filter) return { sql: '', params: [] };
  const parts: string[] = [];
  const marks = filter.topics.map(() => '?').join(',');
  if (filter.topics.length) parts.push(`collection IN (${marks}) OR source_collection IN (${marks})`);
  if (filter.noTopic) parts.push('collection IS NULL');
  if (!parts.length) return { sql: ' AND 0', params: [] };
  return { sql: ` AND (${parts.join(' OR ')})`, params: [...filter.topics, ...filter.topics] };
}

export async function dueCards(db: SQLiteDatabase, nowMs: number, filter: TopicFilter = null): Promise<Card[]> {
  const f = filterSql(filter);
  return db.getAllAsync<Card>(`SELECT * FROM cards WHERE in_pool = 1 AND next_review_at <= ?${f.sql}`, nowMs, ...f.params);
}

export async function countDue(db: SQLiteDatabase, nowMs: number, filter: TopicFilter = null): Promise<number> {
  const f = filterSql(filter);
  const row = await db.getFirstAsync<{ n: number }>(
    `SELECT COUNT(*) AS n FROM cards WHERE in_pool = 1 AND next_review_at <= ?${f.sql}`, nowMs, ...f.params,
  );
  return row?.n ?? 0;
}

export async function stats(db: SQLiteDatabase, maxStage: number) {
  const row = await db.getFirstAsync<{ total: number; learned: number }>(
    'SELECT COUNT(*) AS total, COALESCE(SUM(stage >= ?), 0) AS learned FROM cards WHERE in_pool = 1', maxStage,
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

const markStudied = (db: SQLiteDatabase) => db.runAsync('INSERT OR IGNORE INTO study_days (day) VALUES (?)', dayKey(new Date()));

/** Blitz cards with the name of their topic (own topic, or the added topic a copy came from). */
export async function blitzCards(db: SQLiteDatabase): Promise<(Card & { topic: string | null })[]> {
  return db.getAllAsync(
    `SELECT cards.*, COALESCE(c.name, a.name) AS topic FROM cards
     LEFT JOIN collections c ON c.uuid = cards.collection
     LEFT JOIN added_topics a ON a.uuid = cards.source_collection
     WHERE in_pool = 1 ORDER BY next_review_at`,
  );
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
    await markStudied(db);
  });
}

/** Put cards into the blitz from scratch (or reset their progress there). */
export async function resetIntoPool(db: SQLiteDatabase, uuids: string[]) {
  const at = Date.now();
  await db.withTransactionAsync(async () => {
    for (const uuid of uuids) {
      await db.runAsync(
        'UPDATE cards SET in_pool = 1, stage = 0, correct_count = 0, is_reviewed = 0, next_review_at = ? WHERE uuid = ?', at, uuid,
      );
      await enqueue(db, 'pool', { uuid: Crypto.randomUUID(), card: uuid, action: 'reset', at: new Date(at).toISOString() });
    }
  });
}

export async function removeFromPool(db: SQLiteDatabase, uuid: string) {
  await db.withTransactionAsync(async () => {
    await db.runAsync('UPDATE cards SET in_pool = 0 WHERE uuid = ?', uuid);
    await enqueue(db, 'pool', { uuid: Crypto.randomUUID(), card: uuid, action: 'remove', at: now() });
  });
}

// ------------------------------------------------------------- own cards

export async function topicCards(db: SQLiteDatabase, collection: string | null): Promise<Card[]> {
  return collection
    ? db.getAllAsync<Card>('SELECT * FROM cards WHERE collection = ? ORDER BY created_at', collection)
    : db.getAllAsync<Card>('SELECT * FROM cards WHERE collection IS NULL ORDER BY created_at');
}

export const getCard = (db: SQLiteDatabase, uuid: string) => db.getFirstAsync<Card>('SELECT * FROM cards WHERE uuid = ?', uuid);

export class DuplicateQuestion extends Error {}

async function queueContent(db: SQLiteDatabase, uuid: string, extra: object = {}) {
  const c = await getCard(db, uuid);
  if (!c) return;
  await enqueue(db, 'card', {
    uuid, question: c.question, answer: c.answer, collection: c.collection, content_updated_at: c.content_updated_at, ...extra,
  });
}

/** Add a new own card by hand (it goes straight into the blitz). */
export async function addCard(db: SQLiteDatabase, question: string, answerText: string, collection: string | null) {
  question = question.trim();
  answerText = answerText.trim();
  const dup = await db.getFirstAsync('SELECT uuid FROM cards WHERE question = ?', question);
  if (dup) throw new DuplicateQuestion();
  const ts = now();
  const uuid = Crypto.randomUUID();
  await db.withTransactionAsync(async () => {
    await db.runAsync(
      `INSERT INTO cards (uuid, question, answer, collection, next_review_at, content_updated_at, created_at, in_pool)
       VALUES (?, ?, ?, ?, ?, ?, ?, 1)`,
      uuid, question, answerText, collection, Date.now(), ts, ts,
    );
    await queueContent(db, uuid, { in_pool: true });
  });
}

export async function updateCard(db: SQLiteDatabase, uuid: string, question: string, answerText: string) {
  await db.withTransactionAsync(async () => {
    await db.runAsync('UPDATE cards SET question = ?, answer = ?, content_updated_at = ? WHERE uuid = ?', question.trim(), answerText.trim(), now(), uuid);
    await queueContent(db, uuid);
  });
}

/** Move own cards to another own topic (null = "no topic", i.e. out of the deck). */
export async function moveCards(db: SQLiteDatabase, uuids: string[], collection: string | null) {
  await db.withTransactionAsync(async () => {
    for (const uuid of uuids) {
      await db.runAsync('UPDATE cards SET collection = ?, content_updated_at = ? WHERE uuid = ?', collection, now(), uuid);
      await queueContent(db, uuid);
    }
  });
}

/** Independent copies of own cards in another own topic, not in the blitz. */
export async function copyCards(db: SQLiteDatabase, uuids: string[], collection: string) {
  await db.withTransactionAsync(async () => {
    for (const uuid of uuids) {
      const c = await getCard(db, uuid);
      if (!c) continue;
      const copy = Crypto.randomUUID();
      const ts = now();
      await db.runAsync(
        `INSERT INTO cards (uuid, question, answer, collection, next_review_at, content_updated_at, created_at, in_pool)
         VALUES (?, ?, ?, ?, ?, ?, ?, 0)`,
        copy, c.question, c.answer, collection, Date.now(), ts, ts,
      );
      await queueContent(db, copy, { in_pool: false });
    }
  });
}

export async function deleteCards(db: SQLiteDatabase, uuids: string[]) {
  await db.withTransactionAsync(async () => {
    for (const uuid of uuids) {
      await db.runAsync('DELETE FROM cards WHERE uuid = ?', uuid);
      await enqueue(db, 'delete', { kind: 'card', uuid });
    }
  });
}

// ------------------------------------------------------------ own topics

export async function collections(db: SQLiteDatabase): Promise<(Collection & { count: number })[]> {
  return db.getAllAsync(
    `SELECT collections.*, (SELECT COUNT(*) FROM cards WHERE cards.collection = collections.uuid) AS count
     FROM collections ORDER BY name COLLATE NOCASE`,
  );
}

export const getCollection = (db: SQLiteDatabase, uuid: string) =>
  db.getFirstAsync<Collection>('SELECT * FROM collections WHERE uuid = ?', uuid);

export async function noTopicCount(db: SQLiteDatabase): Promise<number> {
  const row = await db.getFirstAsync<{ n: number }>('SELECT COUNT(*) AS n FROM cards WHERE collection IS NULL');
  return row?.n ?? 0;
}

export async function saveCollection(
  db: SQLiteDatabase, uuid: string | null, fields: { name: string; description: string; tags: string[]; visibility: string },
): Promise<string> {
  const id = uuid ?? Crypto.randomUUID();
  const ts = now();
  const tags = JSON.stringify(fields.tags);
  await db.withTransactionAsync(async () => {
    await db.runAsync(
      'INSERT OR REPLACE INTO collections (uuid, name, description, visibility, tags, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
      id, fields.name.trim(), fields.description.trim(), fields.visibility, tags, ts,
    );
    await enqueue(db, 'collection', { uuid: id, ...fields, name: fields.name.trim(), description: fields.description.trim(), updated_at: ts });
  });
  return id;
}

// ---------------------------------------------------------- added topics

export const addedTopics = (db: SQLiteDatabase) =>
  db.getAllAsync<AddedTopic & { count: number }>(
    `SELECT added_topics.*, (SELECT COUNT(*) FROM added_cards WHERE topic = added_topics.uuid) AS count
     FROM added_topics ORDER BY name COLLATE NOCASE`,
  );

export const getAddedTopic = (db: SQLiteDatabase, uuid: string) =>
  db.getFirstAsync<AddedTopic>('SELECT * FROM added_topics WHERE uuid = ?', uuid);

export const addedCards = (db: SQLiteDatabase, topic: string) =>
  db.getAllAsync<SimpleCard>('SELECT uuid, question, answer FROM added_cards WHERE topic = ? ORDER BY position', topic);

// ------------------------------------------------------------ topic runs

export type TopicRun = {
  collection: string; round: number; queue: string[]; wrong: string[]; round_total: number; correct_count: number; updated_at: string;
};

export async function getRun(db: SQLiteDatabase, collection: string): Promise<TopicRun | null> {
  const r = await db.getFirstAsync<any>('SELECT * FROM topic_runs WHERE collection = ?', collection);
  return r ? { ...r, queue: JSON.parse(r.queue), wrong: JSON.parse(r.wrong) } : null;
}

export async function allRuns(db: SQLiteDatabase): Promise<Record<string, TopicRun>> {
  const rows = await db.getAllAsync<any>('SELECT * FROM topic_runs');
  return Object.fromEntries(rows.map((r) => [r.collection, { ...r, queue: JSON.parse(r.queue), wrong: JSON.parse(r.wrong) }]));
}

export async function saveRun(db: SQLiteDatabase, run: Omit<TopicRun, 'updated_at'>) {
  const ts = now();
  await db.withTransactionAsync(async () => {
    await db.runAsync(
      `INSERT OR REPLACE INTO topic_runs (collection, round, queue, wrong, round_total, correct_count, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      run.collection, run.round, JSON.stringify(run.queue), JSON.stringify(run.wrong), run.round_total, run.correct_count, ts,
    );
    await enqueue(db, 'topic_run', { ...run, updated_at: ts });
    await markStudied(db);
  });
}

export async function deleteRun(db: SQLiteDatabase, collection: string) {
  await db.withTransactionAsync(async () => {
    await db.runAsync('DELETE FROM topic_runs WHERE collection = ?', collection);
    await enqueue(db, 'delete', { kind: 'topic_run', uuid: collection });
  });
}

// ---------------------------------------------------------------- export

/** All own cards as CSV (topic, question, answer, in blitz, stage). */
export async function exportCsv(db: SQLiteDatabase): Promise<string> {
  const rows = await db.getAllAsync<{ topic: string | null; question: string; answer: string; in_pool: number; stage: number }>(
    `SELECT c.name AS topic, question, answer, in_pool, stage FROM cards
     LEFT JOIN collections c ON c.uuid = cards.collection ORDER BY topic, cards.created_at`,
  );
  const esc = (v: string | number | null) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const lines = [['topic', 'question', 'answer', 'in_blitz', 'stage'].join(',')];
  for (const r of rows) lines.push([esc(r.topic), esc(r.question), esc(r.answer), r.in_pool ? 1 : 0, r.stage + 1].join(','));
  return '﻿' + lines.join('\r\n'); // BOM so Excel opens UTF-8 correctly
}
