/**
 * Topic study: pick one of the own or added topics. If its cycle isn't
 * finished, ask whether to continue or start over.
 */
import { router, useFocusEffect } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useState } from 'react';
import { ScrollView, Text } from 'react-native';

import { Sheet } from '@/components/sheet';
import { Muted, Pill, Row, Screen, Section, TopBar } from '@/components/ui';
import { addedTopics, allRuns, collections, type TopicRun } from '@/lib/db';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

type Topic = { uuid: string; name: string; count: number; owner?: string };

export default function SimpleTopics() {
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const { revision } = useSession();
  const [own, setOwn] = useState<Topic[]>([]);
  const [added, setAdded] = useState<Topic[]>([]);
  const [runs, setRuns] = useState<Record<string, TopicRun>>({});
  const [asking, setAsking] = useState<Topic | null>(null);

  useFocusEffect(useCallback(() => {
    void collections(db).then(setOwn);
    void addedTopics(db).then(setAdded);
    void allRuns(db).then(setRuns);
  }, [db, revision]));

  const status = (tp: Topic) => {
    const run = runs[tp.uuid];
    if (!run) return t('simple.cardsN', { n: tp.count });
    if (!run.queue.length && !run.wrong.length) return t('simple.done');
    return t('simple.status', { round: run.round, left: run.queue.length || run.wrong.length });
  };

  const open = (tp: Topic) => {
    if (!runs[tp.uuid]) return router.push(`/simple/${tp.uuid}`);
    setAsking(tp);
  };

  const go = (restart: boolean) => {
    const tp = asking;
    setAsking(null);
    if (tp) router.push({ pathname: '/simple/[id]', params: { id: tp.uuid, restart: restart ? '1' : '' } });
  };

  const run = asking ? runs[asking.uuid] : null;
  const finished = run && !run.queue.length && !run.wrong.length;

  return (
    <Screen>
      <TopBar left="chevron-left" onLeft={() => router.back()} title={t('simple.title')} />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 40 }}>
        {!own.length && !added.length ? <Muted style={{ marginTop: 16 }}>{t('simple.noTopics')}</Muted> : null}
        {own.length ? <Section title={t('lib.mine')} /> : null}
        {own.map((tp) => <Row key={tp.uuid} title={tp.name} subtitle={status(tp)} onPress={() => open(tp)} />)}
        {added.length ? <Section title={t('lib.added')} /> : null}
        {added.map((tp) => <Row key={tp.uuid} title={tp.name} subtitle={`${tp.owner} · ${status(tp)}`} onPress={() => open(tp)} />)}
      </ScrollView>

      <Sheet visible={!!asking} onClose={() => setAsking(null)}>
        <Text style={{ fontSize: 22, fontWeight: '700', color: colors.fg, textAlign: 'center' }}>{asking?.name}</Text>
        {run && !finished ? (
          <>
            <Muted style={{ fontSize: 15, textAlign: 'center', marginTop: 8 }}>
              {t('simple.continueText', { round: run.round, left: run.queue.length || run.wrong.length, total: run.round_total })}
            </Muted>
            <Pill title={t('simple.continue')} onPress={() => go(false)} style={{ marginTop: 24 }} />
            <Pill title={t('simple.restart')} ghost onPress={() => go(true)} style={{ marginTop: 10 }} />
          </>
        ) : (
          <>
            <Muted style={{ fontSize: 15, textAlign: 'center', marginTop: 8 }}>{t('simple.topicDone')}</Muted>
            <Pill title={t('simple.again')} onPress={() => go(true)} style={{ marginTop: 24 }} />
          </>
        )}
      </Sheet>
    </Screen>
  );
}
