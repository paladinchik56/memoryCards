/**
 * "Add to blitz" with the skip / reset-progress question for cards that are
 * already there. Own cards are handled locally (synced later); someone
 * else's cards go through the API (they become linked personal copies).
 */
import { useSQLiteContext } from 'expo-sqlite';
import { useState } from 'react';
import { Alert } from 'react-native';

import { ConflictSheet } from './sheet';
import { getCard, resetIntoPool } from '@/lib/db';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

type Pending = { uuids: string[]; conflicts: { uuid: string; question: string }[]; apply: (reset: string[]) => Promise<void> };

export function useBlitzAdder(onDone?: () => void) {
  const db = useSQLiteContext();
  const { t } = useSettings();
  const { api, syncNow, scheduleSync } = useSession();
  const [pending, setPending] = useState<Pending | null>(null);

  const run = async (p: Pending) => {
    if (p.conflicts.length) return setPending(p);
    await p.apply([]);
  };

  /** Own cards (local database). */
  const addOwn = async (uuids: string[]) => {
    const cards = (await Promise.all(uuids.map((u) => getCard(db, u)))).filter((c) => c !== null);
    const conflicts = cards.filter((c) => c.in_pool).map((c) => ({ uuid: c.uuid, question: c.question }));
    const fresh = cards.filter((c) => !c.in_pool).map((c) => c.uuid);
    await run({
      uuids,
      conflicts,
      apply: async (reset) => {
        await resetIntoPool(db, [...fresh, ...reset]);
        scheduleSync();
        Alert.alert(t('lib.blitzResult', { added: fresh.length, reset: reset.length, skipped: conflicts.length - reset.length }));
        onDone?.();
      },
    });
  };

  /** Cards of someone else's topic (needs the server). */
  const addForeign = async (shareToken: string, uuids: string[]) => {
    if (!api) return;
    try {
      const topic = await api.shared(shareToken);
      const picked = topic.cards.filter((c) => uuids.includes(c.uuid));
      await run({
        uuids,
        conflicts: picked.filter((c) => c.in_blitz).map((c) => ({ uuid: c.uuid, question: c.question })),
        apply: async (reset) => {
          try {
            const res = await api.addToBlitz(shareToken, uuids, reset);
            await syncNow();
            Alert.alert(t('lib.blitzResult', res));
            onDone?.();
          } catch {
            Alert.alert(t('lib.needNetwork'));
          }
        },
      });
    } catch {
      Alert.alert(t('lib.needNetwork'));
    }
  };

  const sheet = (
    <ConflictSheet
      visible={!!pending}
      newCount={pending ? pending.uuids.length - pending.conflicts.length : 0}
      conflicts={pending?.conflicts ?? []}
      onClose={() => setPending(null)}
      onConfirm={(reset) => {
        const p = pending;
        setPending(null);
        void p?.apply(reset);
      }}
    />
  );

  return { addOwn, addForeign, sheet };
}
