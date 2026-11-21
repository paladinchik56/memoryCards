/**
 * One sync round trip: push everything in `outbox`, pull what changed on the
 * server since the last sync, apply it locally. Protocol: api/views.py `sync`.
 */
import type { SQLiteDatabase } from 'expo-sqlite';

import type { Api } from './api';
import { getMeta, setMeta } from './db';

type OutboxRow = { id: number; kind: string; payload: string };

export async function syncOnce(db: SQLiteDatabase, api: Api): Promise<{ rejected: number }> {
  const rows = await db.getAllAsync<OutboxRow>('SELECT * FROM outbox ORDER BY id');
  const pushedIds = rows.map((r) => r.id);
  const reviews: object[] = [];
  const pool: object[] = [];
  const deleted: object[] = [];
  // Latest version of each card / topic / run wins.
  const cards = new Map<string, any>();
  const collections = new Map<string, object>();
  const runs = new Map<string, object>();
  for (const row of rows) {
    const p = JSON.parse(row.payload);
    if (row.kind === 'review') reviews.push(p);
    else if (row.kind === 'pool') pool.push(p);
    else if (row.kind === 'delete') deleted.push(p);
    else if (row.kind === 'card') cards.set(p.uuid, { ...cards.get(p.uuid), ...p });
    else if (row.kind === 'collection') collections.set(p.uuid, p);
    else if (row.kind === 'topic_run') runs.set(p.collection, p);
  }

  const since = await getMeta(db, 'since');
  const res = await api.sync({
    since,
    reviews,
    pool,
    cards: [...cards.values()],
    collections: [...collections.values()],
    deleted,
    topic_runs: [...runs.values()],
  });

  await db.withTransactionAsync(async () => {
    // Changes made while the request was in flight are still in the outbox:
    // keep the local state of those cards and runs, the next sync sends them.
    const notPushed = await db.getAllAsync<{ kind: string; payload: string }>(
      `SELECT kind, payload FROM outbox WHERE id NOT IN (${pushedIds.map(() => '?').join(',') || 'NULL'})`, ...pushedIds,
    );
    const pendingCards = new Set<string>();
    const pendingRuns = new Set<string>();
    for (const r of notPushed) {
      const p = JSON.parse(r.payload);
      if (r.kind === 'review' || r.kind === 'pool') pendingCards.add(p.card);
      if (r.kind === 'topic_run') pendingRuns.add(p.collection);
    }

    for (const c of res.collections) {
      await db.runAsync(
        'INSERT OR REPLACE INTO collections (uuid, name, description, visibility, tags, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
        c.uuid, c.name, c.description, c.visibility, JSON.stringify(c.tags ?? []), c.updated_at,
      );
    }
    for (const c of res.cards) {
      if (pendingCards.has(c.uuid)) {
        await db.runAsync(
          'UPDATE cards SET question = ?, answer = ?, collection = ?, source_collection = ?, content_updated_at = ? WHERE uuid = ?',
          c.question, c.answer, c.collection, c.source_collection, c.content_updated_at, c.uuid,
        );
        continue;
      }
      await db.runAsync(
        `INSERT OR REPLACE INTO cards
           (uuid, question, answer, collection, source_collection, in_pool, stage, correct_count, is_reviewed,
            next_review_at, content_updated_at, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        c.uuid, c.question, c.answer, c.collection, c.source_collection, c.in_pool ? 1 : 0, c.stage, c.correct_count,
        c.is_reviewed ? 1 : 0, Date.parse(c.next_review_at), c.content_updated_at, c.created_at,
      );
    }
    for (const r of res.topic_runs) {
      if (pendingRuns.has(r.collection)) continue;
      await db.runAsync(
        `INSERT OR REPLACE INTO topic_runs (collection, round, queue, wrong, round_total, correct_count, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        r.collection, r.round, JSON.stringify(r.queue), JSON.stringify(r.wrong), r.round_total, r.correct_count, r.updated_at,
      );
    }
    for (const d of res.deleted) {
      if (d.kind === 'card') await db.runAsync('DELETE FROM cards WHERE uuid = ?', d.uuid);
      if (d.kind === 'topic_run' && !pendingRuns.has(d.uuid)) await db.runAsync('DELETE FROM topic_runs WHERE collection = ?', d.uuid);
      if (d.kind === 'collection') {
        await db.runAsync('DELETE FROM collections WHERE uuid = ?', d.uuid);
        await db.runAsync('UPDATE cards SET collection = NULL WHERE collection = ?', d.uuid);
      }
    }

    // Added topics come in full every time: replace them.
    await db.execAsync('DELETE FROM added_topics; DELETE FROM added_cards;');
    for (const tp of res.added_topics) {
      await db.runAsync(
        'INSERT INTO added_topics (uuid, share_token, name, description, tags, owner) VALUES (?, ?, ?, ?, ?, ?)',
        tp.uuid, tp.share_token, tp.name, tp.description, JSON.stringify(tp.tags ?? []), tp.owner,
      );
      for (const [i, c] of tp.cards.entries()) {
        await db.runAsync(
          'INSERT OR REPLACE INTO added_cards (uuid, topic, question, answer, position) VALUES (?, ?, ?, ?, ?)',
          c.uuid, tp.uuid, c.question, c.answer, i,
        );
      }
    }
    // Runs of topics that are neither own nor added anymore are useless.
    await db.runAsync(
      'DELETE FROM topic_runs WHERE collection NOT IN (SELECT uuid FROM collections) AND collection NOT IN (SELECT uuid FROM added_topics)',
    );

    if (pushedIds.length) {
      await db.runAsync(`DELETE FROM outbox WHERE id IN (${pushedIds.map(() => '?').join(',')})`, ...pushedIds);
    }
    await setMeta(db, 'since', res.server_time);
    await setMeta(db, 'last_sync', new Date().toISOString());
  });
  return { rejected: res.rejected.length };
}
