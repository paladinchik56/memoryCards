/**
 * Blitz study: due cards of the blitz, optionally filtered by topics and a stage range.
 * Answers count in the blitz only; topic runs (simple study) keep their own progress.
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
import { MAX_STAGE, STAGE_INTERVALS_S } from '@/lib/scheduler';
import { formatDuration } from '@/lib/i18n';
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

  const nTopics = filter ? filter.topics.length + (filter.noTopic ? 1 : 0) : 0;
  const filterLabel = (nTopics ? t('blitz.topicsN', { n: nTopics }) : t('blitz.allTopics'))
    + (filter?.stages ? ' · ' + t('blitz.stagesRange', { lo: filter.stages[0] + 1, hi: filter.stages[1] + 1 }) : '');
  const bottom = Math.max(insets.bottom, 12);

  return (
    <Screen edges={['top', 'bottom']}>
      <TopBar
        left="x"
        onLeft={() => router.back()}
        right={<Muted style={{ fontSize: 14 }}>{left}</Muted>}
        title={filter ? filterLabel : undefined}
      />

      <View style={{ flex: 1 }}>
      {!loaded ? null : card ? (
        <FlashCard cardKey={`${card.uuid}:${card.correct_count}:${card.next_review_at}`} question={card.question} answer={card.answer} onAnswer={(c) => void grade(c)} onRemove={() => void removeCurrent()} />
      ) : (
        <View style={st.empty}>
          <Text style={[st.big, { color: colors.fg }]}>0</Text>
          <Muted style={{ fontSize: 16, textAlign: 'center' }}>{t('blitz.empty')}</Muted>
        </View>
      )}
      <FilterButton active={!!filter} label={t('blitz.filter')} onPress={() => setFilterOpen(true)} />
      </View>

      <Pressable style={[st.corner, { right: 24, bottom }]} onPress={() => router.push('/add-card')} hitSlop={10}>
        <Icon name="plus" size={18} color={colors.muted} />
        <Muted style={{ fontSize: 14 }}>{t('blitz.addCard')}</Muted>
      </Pressable>

      <TopicFilterSheet visible={filterOpen} value={filter} onClose={() => setFilterOpen(false)} onApply={(f) => { setFilter(f); setFilterOpen(false); }} />
    </Screen>
  );
}

/** Filter button in the card's top-right corner: the pill style of the app with a soft
 * fill, so it stands out a little; filled dark with a dot while a filter is on. */
function FilterButton({ active, label, onPress }: { active: boolean; label: string; onPress: () => void }) {
  const { colors } = useSettings();
  const fg = active ? colors.bg : colors.fg;
  return (
    <Pressable
      onPress={onPress}
      hitSlop={8}
      accessibilityRole="button"
      style={[st.filterBtn, active ? { backgroundColor: colors.fg, borderColor: colors.fg } : { backgroundColor: colors.soft, borderColor: colors.line }]}
    >
      <Icon name="filter" size={14} color={fg} />
      <Text style={{ color: fg, fontSize: 13, fontWeight: '600' }}>{label}</Text>
      {active ? <View style={[st.dot, { backgroundColor: colors.bg }]} /> : null}
    </Pressable>
  );
}

/** Own topics + added topics + "no topic" and a stage range; each topic shows how many
 * of its blitz cards are due within that range. */
function TopicFilterSheet({ visible, value, onClose, onApply }: {
  visible: boolean; value: TopicFilter; onClose: () => void; onApply: (f: TopicFilter) => void;
}) {
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const [topics, setTopics] = useState<{ uuid: string; name: string; due: number }[]>([]);
  const [noTopicDue, setNoTopicDue] = useState(0);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [noTopic, setNoTopic] = useState(false);
  const [[lo, hi], setStages] = useState<[number, number]>([0, MAX_STAGE]);

  useEffect(() => {
    if (!visible) return;
    setPicked(new Set(value?.topics ?? []));
    setNoTopic(value?.noTopic ?? false);
    setStages(value?.stages ?? [0, MAX_STAGE]);
  }, [visible, value]);

  useEffect(() => {
    if (!visible) return;
    (async () => {
      const now = Date.now();
      const stages: [number, number] = [lo, hi];
      const list = [...(await collections(db)), ...(await addedTopics(db))];
      setTopics(await Promise.all(list.map(async (c) => ({ uuid: c.uuid, name: c.name, due: await countDue(db, now, { topics: [c.uuid], noTopic: false, stages }) }))));
      setNoTopicDue(await countDue(db, now, { topics: [], noTopic: true, stages }));
    })();
  }, [visible, db, lo, hi]);

  const row = (key: string, name: string, due: number, on: boolean, toggle: () => void) => (
    <Pressable key={key} onPress={toggle} style={[st.checkRow, { borderBottomColor: colors.line }]}>
      <Checkbox on={on} />
      <Text style={{ flex: 1, color: colors.fg, fontSize: 16 }}>{name}</Text>
      <Muted style={{ fontSize: 13 }}>{due}</Muted>
    </Pressable>
  );

  // Picking "from" above "to" (or the other way round) drags the other end along.
  const stageRow = (label: string, current: number, pick: (n: number) => void) => (
    <View style={st.stageRow}>
      <Muted style={{ width: 28, fontSize: 14 }}>{label}</Muted>
      {STAGE_INTERVALS_S.map((_, i) => <Chip key={i} title={String(i + 1)} active={i === current} onPress={() => pick(i)} />)}
    </View>
  );

  const apply = () => {
    const allStages = lo === 0 && hi === MAX_STAGE;
    if (!picked.size && !noTopic && allStages) return onApply(null);
    onApply({ topics: [...picked], noTopic, ...(allStages ? {} : { stages: [lo, hi] as [number, number] }) });
  };

  return (
    <Sheet visible={visible} onClose={onClose}>
      <Text style={{ fontSize: 20, fontWeight: '700', color: colors.fg }}>{t('blitz.filterTitle')}</Text>
      <Muted style={{ fontSize: 14, marginTop: 4, marginBottom: 8 }}>{t('blitz.filterHint')}</Muted>
      <ScrollView style={{ maxHeight: 300 }}>
        {topics.map((tp) => row(tp.uuid, tp.name, tp.due, picked.has(tp.uuid), () => {
          const n = new Set(picked);
          if (n.has(tp.uuid)) n.delete(tp.uuid); else n.add(tp.uuid);
          setPicked(n);
        }))}
        {row('none', t('lib.noTopic'), noTopicDue, noTopic, () => setNoTopic(!noTopic))}
      </ScrollView>
      <Text style={{ fontSize: 16, fontWeight: '600', color: colors.fg, marginTop: 16 }}>{t('blitz.stages')}</Text>
      {stageRow(t('blitz.from'), lo, (n) => setStages([n, Math.max(n, hi)]))}
      {stageRow(t('blitz.to'), hi, (n) => setStages([Math.min(lo, n), n]))}
      <Muted style={{ fontSize: 13, marginTop: 6 }}>
        {t('blitz.stagesHint', { from: formatDuration(STAGE_INTERVALS_S[lo] * 1000, t), to: formatDuration(STAGE_INTERVALS_S[hi] * 1000, t) })}
      </Muted>
      <Pill title={t('blitz.show')} onPress={apply} style={{ marginTop: 18 }} />
    </Sheet>
  );
}

const st = StyleSheet.create({
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 40, paddingBottom: 80 },
  big: { fontSize: 120, fontWeight: '600', letterSpacing: -6, lineHeight: 130 },
  corner: { position: 'absolute', flexDirection: 'row', alignItems: 'center', gap: 6 },
  // FlashCard area padding (24 / 20) + 14 inside the card.
  filterBtn: { position: 'absolute', top: 34, right: 38, flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderRadius: 999, paddingVertical: 7, paddingHorizontal: 13 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  stageRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth },
});
