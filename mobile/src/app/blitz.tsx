/**
 * Blitz study: due cards of the blitz, optionally filtered by topics.
 * Order and comebacks after a wrong answer: lib/blitz.ts.
 */
import { router, useFocusEffect } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { FlashCard } from '@/components/flashcard';
import { Checkbox, Sheet } from '@/components/sheet';
import { Chip, Icon, Muted, Pill, Screen, TopBar } from '@/components/ui';
import { afterAnswer, chooseNext, newState, type BlitzState } from '@/lib/blitz';
import { addedTopics, answer, collections, countDue, dueCards, removeFromPool, type Card, type TopicFilter } from '@/lib/db';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function Blitz() {
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const { scheduleSync } = useSession();
  const insets = useSafeAreaInsets();

  const [card, setCard] = useState<Card | null>(null);
  const [left, setLeft] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [filter, setFilter] = useState<TopicFilter>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const state = useRef<BlitzState>(newState());

  const next = useCallback(async () => {
    const now = Date.now();
    const due = await dueCards(db, now, filter);
    setLeft(due.length);
    setCard(chooseNext(due, now, state.current));
    setLoaded(true);
  }, [db, filter]);

  // Reload when coming back (e.g. from "add card") and when the filter changes.
  useFocusEffect(useCallback(() => { void next(); }, [next]));

  // Nothing due: check again now and then, short stages come back quickly.
  useEffect(() => {
    if (card) return;
    const id = setInterval(() => void next(), 10000);
    return () => clearInterval(id);
  }, [card, next]);

  const grade = async (correct: boolean) => {
    if (!card) return;
    await answer(db, card, correct);
    state.current = afterAnswer(state.current, card.uuid, correct);
    scheduleSync();
    await next();
  };

  const removeCurrent = async () => {
    if (!card) return;
    await removeFromPool(db, card.uuid);
    state.current = { ...state.current, last: card.uuid };
    scheduleSync();
    await next();
  };

  const filterLabel = !filter ? t('blitz.allTopics') : t('blitz.topicsN', { n: filter.topics.length + (filter.noTopic ? 1 : 0) });
  const bottom = Math.max(insets.bottom, 12);

  return (
    <Screen edges={['top', 'bottom']}>
      <TopBar left="x" onLeft={() => router.back()} right={<Muted style={{ fontSize: 14 }}>{left}</Muted>} />
      <View style={{ alignItems: 'center', marginTop: -4 }}><Chip title={filterLabel} icon="filter" onPress={() => setFilterOpen(true)} /></View>

      {!loaded ? null : card ? (
        <FlashCard cardKey={`${card.uuid}:${card.correct_count}:${card.next_review_at}`} question={card.question} answer={card.answer} onAnswer={(c) => void grade(c)} />
      ) : (
        <View style={st.empty}>
          <Text style={[st.big, { color: colors.fg }]}>0</Text>
          <Muted style={{ fontSize: 16, textAlign: 'center' }}>{t('blitz.empty')}</Muted>
        </View>
      )}

      {card ? (
        <Pressable style={[st.corner, { left: 24, bottom }]} onPress={() => void removeCurrent()} hitSlop={10}>
          <Icon name="trash-2" size={18} color={colors.muted} />
          <Muted style={{ fontSize: 14 }}>{t('blitz.remove')}</Muted>
        </Pressable>
      ) : null}
      <Pressable style={[st.corner, { right: 24, bottom }]} onPress={() => router.push('/add-card')} hitSlop={10}>
        <Icon name="plus" size={18} color={colors.muted} />
        <Muted style={{ fontSize: 14 }}>{t('blitz.addCard')}</Muted>
      </Pressable>

      <TopicFilterSheet visible={filterOpen} value={filter} onClose={() => setFilterOpen(false)} onApply={(f) => { setFilter(f); setFilterOpen(false); }} />
    </Screen>
  );
}

/** Own topics + added topics + "no topic"; each with how many of its blitz cards are due. */
function TopicFilterSheet({ visible, value, onClose, onApply }: {
  visible: boolean; value: TopicFilter; onClose: () => void; onApply: (f: TopicFilter) => void;
}) {
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const [topics, setTopics] = useState<{ uuid: string; name: string; due: number }[]>([]);
  const [noTopicDue, setNoTopicDue] = useState(0);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [noTopic, setNoTopic] = useState(false);

  useEffect(() => {
    if (!visible) return;
    (async () => {
      const now = Date.now();
      const list = [...(await collections(db)), ...(await addedTopics(db))];
      setTopics(await Promise.all(list.map(async (c) => ({ uuid: c.uuid, name: c.name, due: await countDue(db, now, { topics: [c.uuid], noTopic: false }) }))));
      setNoTopicDue(await countDue(db, now, { topics: [], noTopic: true }));
      setPicked(new Set(value?.topics ?? []));
      setNoTopic(value?.noTopic ?? false);
    })();
  }, [visible, db, value]);

  const row = (key: string, name: string, due: number, on: boolean, toggle: () => void) => (
    <Pressable key={key} onPress={toggle} style={[st.checkRow, { borderBottomColor: colors.line }]}>
      <Checkbox on={on} />
      <Text style={{ flex: 1, color: colors.fg, fontSize: 16 }}>{name}</Text>
      <Muted style={{ fontSize: 13 }}>{due}</Muted>
    </Pressable>
  );

  return (
    <Sheet visible={visible} onClose={onClose}>
      <Text style={{ fontSize: 20, fontWeight: '700', color: colors.fg }}>{t('blitz.filterTitle')}</Text>
      <Muted style={{ fontSize: 14, marginTop: 4, marginBottom: 8 }}>{t('blitz.filterHint')}</Muted>
      <ScrollView style={{ maxHeight: 360 }}>
        {topics.map((tp) => row(tp.uuid, tp.name, tp.due, picked.has(tp.uuid), () => {
          const n = new Set(picked);
          if (n.has(tp.uuid)) n.delete(tp.uuid); else n.add(tp.uuid);
          setPicked(n);
        }))}
        {row('none', t('lib.noTopic'), noTopicDue, noTopic, () => setNoTopic(!noTopic))}
      </ScrollView>
      <Pill title={t('blitz.show')} onPress={() => onApply(picked.size || noTopic ? { topics: [...picked], noTopic } : null)} style={{ marginTop: 18 }} />
    </Sheet>
  );
}

const st = StyleSheet.create({
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 40, paddingBottom: 80 },
  big: { fontSize: 120, fontWeight: '600', letterSpacing: -6, lineHeight: 130 },
  corner: { position: 'absolute', flexDirection: 'row', alignItems: 'center', gap: 6 },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth },
});
