/**
 * A topic study cycle: round 1 = every card of the topic in random order,
 * each next round = the cards answered wrong in the previous one, until a
 * round has no mistakes. Saved after every answer; doesn't touch the blitz.
 */
import { router, useLocalSearchParams } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { FlashCard } from '@/components/flashcard';
import { Muted, Pill, Screen, TopBar } from '@/components/ui';
import {
  addedCards, deleteRun, getAddedTopic, getCollection, getRun, saveRun, topicCards, type SimpleCard, type TopicRun,
} from '@/lib/db';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

const shuffle = <T,>(items: T[]): T[] => {
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

type Run = Omit<TopicRun, 'updated_at'>;

export default function SimpleRun() {
  const { id, restart } = useLocalSearchParams<{ id: string; restart?: string }>();
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const { scheduleSync } = useSession();
  const [name, setName] = useState('');
  const [cards, setCards] = useState<Map<string, SimpleCard>>(new Map());
  const [run, setRun] = useState<Run | null>(null);

  const freshRun = useCallback((uuids: string[], round = 1): Run => (
    { collection: id, round, queue: shuffle(uuids), wrong: [], round_total: uuids.length, correct_count: 0 }
  ), [id]);

  useEffect(() => {
    (async () => {
      const own = await getCollection(db, id);
      const list: SimpleCard[] = own ? await topicCards(db, id) : await addedCards(db, id);
      setName(own?.name ?? (await getAddedTopic(db, id))?.name ?? '');
      const byId = new Map(list.map((c) => [c.uuid, c]));
      setCards(byId);
      let r: Run | null = restart ? null : await getRun(db, id);
      if (r) {
        // Cards deleted from the topic since the run started just drop out.
        r = { ...r, queue: r.queue.filter((u) => byId.has(u)), wrong: r.wrong.filter((u) => byId.has(u)) };
      } else {
        if (restart) await deleteRun(db, id);
        r = freshRun([...byId.keys()]);
        if (r.round_total) await saveRun(db, r);
        scheduleSync();
      }
      setRun(r);
    })();
  }, [db, id, restart, freshRun, scheduleSync]);

  const persist = async (r: Run) => {
    setRun(r);
    await saveRun(db, r);
    scheduleSync();
  };

  const onAnswer = (correct: boolean) => {
    if (!run || !run.queue.length) return;
    const [current, ...rest] = run.queue;
    void persist({
      ...run,
      queue: rest,
      wrong: correct ? run.wrong : [...run.wrong, current],
      correct_count: run.correct_count + (correct ? 1 : 0),
    });
  };

  const nextRound = () => run && void persist({ ...freshRun(run.wrong, run.round + 1) });
  const again = async () => {
    await deleteRun(db, id);
    await persist(freshRun([...cards.keys()]));
  };

  const current = run?.queue.length ? cards.get(run.queue[0]) : undefined;
  const position = run ? run.round_total - run.queue.length + 1 : 0;

  return (
    <Screen edges={['top', 'bottom']}>
      <TopBar
        left="x" onLeft={() => router.back()} title={name}
        right={current && run ? <Muted style={{ fontSize: 14 }}>{position} / {run.round_total}</Muted> : null}
      />
      {!run ? null : !run.round_total && !run.queue.length ? (
        <Muted style={{ textAlign: 'center', marginTop: 60 }}>{t('simple.empty')}</Muted>
      ) : current ? (
        <>
          <Muted style={st.round}>{t('simple.pass', { n: run.round }).toUpperCase()}</Muted>
          <FlashCard cardKey={`${run.round}:${position}`} question={current.question} answer={current.answer} onAnswer={onAnswer} />
        </>
      ) : (
        <View style={st.result}>
          <Muted style={st.round}>{t('simple.passDone', { n: run.round }).toUpperCase()}</Muted>
          <Text style={[st.big, { color: colors.fg }]}>
            {run.correct_count}<Text style={{ fontSize: 48, color: colors.muted }}>/{run.round_total}</Text>
          </Text>
          <Muted style={{ fontSize: 16 }}>{t('simple.correctOf')}</Muted>
          {run.wrong.length ? (
            <Pill title={t('simple.next', { n: run.wrong.length })} onPress={nextRound} style={st.wide} />
          ) : (
            <>
              <Text style={[st.done, { color: colors.fg }]}>{t('simple.topicDone')}</Text>
              <Pill title={t('simple.again')} onPress={() => void again()} style={st.wide} />
            </>
          )}
          <Pill title={t('simple.finish')} ghost onPress={() => router.back()} style={[st.wide, { marginTop: 12 }]} />
        </View>
      )}
    </Screen>
  );
}

const st = StyleSheet.create({
  round: { textAlign: 'center', fontSize: 13, fontWeight: '600', letterSpacing: 1 },
  result: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32, paddingBottom: 60 },
  big: { fontSize: 96, fontWeight: '600', letterSpacing: -4, marginTop: 18 },
  done: { fontSize: 16, fontWeight: '500', marginTop: 24, textAlign: 'center' },
  wide: { alignSelf: 'stretch', marginTop: 32 },
});
