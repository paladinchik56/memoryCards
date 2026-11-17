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
  const cards = new Map<string, object>(); // latest version of each card wins
  const collections = new Map<string, object>();
  const deleted: object[] = [];
  for (const row of rows) {
    const p = JSON.parse(row.payload);
    if (row.kind === 'review') reviews.push(p);
    else if (row.kind === 'card') cards.set(p.uuid, p);
    else if (row.kind === 'collection') collections.set(p.uuid, p);
    else if (row.kind === 'delete') deleted.push(p);
  }

  const since = await getMeta(db, 'since');
  const res = await api.sync({
    since,
    reviews,
    cards: [...cards.values()],
    collections: [...collections.values()],
    deleted,
  });

  await db.withTransactionAsync(async () => {
    // Reviews made while the request was in flight are still in the outbox:
    // keep the local progress of those cards, the next sync sends them.
    const pending = new Set(
      (
        await db.getAllAsync<{ payload: string }>(
          `SELECT payload FROM outbox WHERE kind = 'review' AND id NOT IN (${pushedIds.map(() => '?').join(',') || 'NULL'})`,
          ...pushedIds,
        )
      ).map((r) => JSON.parse(r.payload).card as string),
    );

    for (const c of res.collections) {
      await db.runAsync(
        'INSERT OR REPLACE INTO collections (uuid, name, description, visibility, updated_at) VALUES (?, ?, ?, ?, ?)',
        c.uuid, c.name, c.description, c.visibility, c.updated_at,
      );
    }
    for (const c of res.cards) {
      if (pending.has(c.uuid)) {
        await db.runAsync(
          'UPDATE cards SET question = ?, answer = ?, collection = ?, content_updated_at = ? WHERE uuid = ?',
          c.question, c.answer, c.collection, c.content_updated_at, c.uuid,
        );
        continue;
      }
      await db.runAsync(
        `INSERT OR REPLACE INTO cards
           (uuid, question, answer, collection, stage, correct_count, is_reviewed, next_review_at, content_updated_at, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        c.uuid, c.question, c.answer, c.collection, c.stage, c.correct_count, c.is_reviewed ? 1 : 0,
        Date.parse(c.next_review_at), c.content_updated_at, c.created_at,
      );
    }
    for (const d of res.deleted) {
      if (d.kind === 'card') await db.runAsync('DELETE FROM cards WHERE uuid = ?', d.uuid);
      if (d.kind === 'collection') {
        await db.runAsync('DELETE FROM collections WHERE uuid = ?', d.uuid);
        await db.runAsync('UPDATE cards SET collection = NULL WHERE collection = ?', d.uuid);
      }
    }
    // A rejected new card (e.g. duplicate question) would otherwise linger locally forever.
    for (const r of res.rejected) {
      if (r.kind === 'card' && r.uuid && r.reason !== 'not_owner') {
        const known = res.cards.some((c) => c.uuid === r.uuid);
        if (!known) await db.runAsync('DELETE FROM cards WHERE uuid = ?', r.uuid);
      }
    }
    if (pushedIds.length) {
      await db.runAsync(`DELETE FROM outbox WHERE id IN (${pushedIds.map(() => '?').join(',')})`, ...pushedIds);
    }
    await setMeta(db, 'since', res.server_time);
    await setMeta(db, 'last_sync', new Date().toISOString());
  });
  return { rejected: res.rejected.length };
}
