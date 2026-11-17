/**
 * Blitz study. Tap the card to see the answer, then swipe right (right) or
 * left (wrong), or use the buttons. Order and comebacks: lib/blitz.ts.
 */
import { router, useFocusEffect } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Modal, PanResponder, Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Chip, Icon, Muted, Pill, Screen, TopBar } from '@/components/ui';
import { afterAnswer, chooseNext, newState, type BlitzState } from '@/lib/blitz';
import { answer, collections, countDue, dueCards, type Card, type TopicFilter } from '@/lib/db';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

const SWIPE = 110;

export default function Blitz() {
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const { scheduleSync } = useSession();
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();

  const [card, setCard] = useState<Card | null>(null);
  const [left, setLeft] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [flipped, setFlipped] = useState(false);
  const [filter, setFilter] = useState<TopicFilter>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const state = useRef<BlitzState>(newState());
  const busy = useRef(false);
  const pan = useRef(new Animated.ValueXY()).current;

  const next = useCallback(async () => {
    const now = Date.now();
    const due = await dueCards(db, now, filter);
    setLeft(due.length);
    setCard(chooseNext(due, now, state.current));
    setFlipped(false);
    pan.setValue({ x: 0, y: 0 });
    setLoaded(true);
  }, [db, filter, pan]);

  // Reload when coming back (e.g. from "add card") and when the filter changes.
  useFocusEffect(useCallback(() => { void next(); }, [next]));

  // Nothing due: check again now and then, short stages come back quickly.
  useEffect(() => {
    if (card) return;
    const id = setInterval(() => void next(), 10000);
    return () => clearInterval(id);
  }, [card, next]);

  const grade = useCallback(async (correct: boolean) => {
    if (!card || busy.current) return;
    busy.current = true;
    try {
      await answer(db, card, correct);
      state.current = afterAnswer(state.current, card.uuid, correct);
      scheduleSync();
      await next();
    } finally {
      busy.current = false;
    }
  }, [card, db, next, scheduleSync]);

  const flyOut = (correct: boolean) => {
    Animated.timing(pan, { toValue: { x: (correct ? 1 : -1) * width * 1.3, y: 0 }, duration: 180, useNativeDriver: true })
      .start(() => void grade(correct));
  };

  const flippedRef = useRef(flipped);
  flippedRef.current = flipped;
  const flyRef = useRef(flyOut);
  flyRef.current = flyOut;

  const responder = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) => flippedRef.current && Math.abs(g.dx) > 8 && Math.abs(g.dx) > Math.abs(g.dy),
      onPanResponderMove: (_, g) => pan.setValue({ x: g.dx, y: g.dy * 0.2 }),
      onPanResponderRelease: (_, g) => {
        if (Math.abs(g.dx) > SWIPE) flyRef.current(g.dx > 0);
        else Animated.spring(pan, { toValue: { x: 0, y: 0 }, useNativeDriver: true }).start();
      },
      onPanResponderTerminate: () => Animated.spring(pan, { toValue: { x: 0, y: 0 }, useNativeDriver: true }).start(),
    }),
  ).current;

  const rotate = pan.x.interpolate({ inputRange: [-width, 0, width], outputRange: ['-12deg', '0deg', '12deg'] });
  const rightOpacity = pan.x.interpolate({ inputRange: [0, SWIPE], outputRange: [0, 1], extrapolate: 'clamp' });
  const wrongOpacity = pan.x.interpolate({ inputRange: [-SWIPE, 0], outputRange: [1, 0], extrapolate: 'clamp' });

  const filterLabel = !filter ? t('blitz.allTopics') : t('blitz.topicsN', { n: filter.topics.length + (filter.noTopic ? 1 : 0) });

  return (
    <Screen edges={['top', 'bottom']}>
      <TopBar
        left="x"
        onLeft={() => router.back()}
        title=""
        right={<Muted style={{ fontSize: 14 }}>{left}</Muted>}
      />
      <View style={st.filterRow}><Chip title={filterLabel} icon="filter" onPress={() => setFilterOpen(true)} /></View>

      {!loaded ? null : card ? (
        <>
          <View style={st.cardArea}>
            <Animated.View
              {...responder.panHandlers}
              style={[st.card, { backgroundColor: colors.bg, borderColor: colors.line, transform: [{ translateX: pan.x }, { translateY: pan.y }, { rotate }] }]}
            >
              <Pressable style={st.cardInner} onPress={() => setFlipped((f) => !f)}>
                <Text style={[st.face, { color: colors.muted }]}>{(flipped ? t('blitz.answer') : t('blitz.question')).toUpperCase()}</Text>
                <ScrollView contentContainerStyle={st.textWrap}>
                  <Text style={[st.text, { color: colors.fg }]}>{flipped ? card.answer : card.question}</Text>
                </ScrollView>
                {!flipped ? <Muted style={st.hint}>{t('blitz.tapToFlip')}</Muted> : null}
              </Pressable>
              <Animated.Text style={[st.stamp, st.stampRight, { color: colors.fg, borderColor: colors.fg, opacity: rightOpacity }]}>{t('blitz.right').toUpperCase()}</Animated.Text>
              <Animated.Text style={[st.stamp, st.stampWrong, { color: colors.fg, borderColor: colors.fg, opacity: wrongOpacity }]}>{t('blitz.wrong').toUpperCase()}</Animated.Text>
            </Animated.View>
          </View>
          <View style={[st.bottom, { opacity: flipped ? 1 : 0 }]} pointerEvents={flipped ? 'auto' : 'none'}>
            <Pill title={t('blitz.wrong')} ghost onPress={() => flyOut(false)} style={{ flex: 1 }} />
            <Pill title={t('blitz.right')} onPress={() => flyOut(true)} style={{ flex: 1 }} />
          </View>
        </>
      ) : (
        <View style={st.empty}>
          <Text style={[st.big, { color: colors.fg }]}>0</Text>
          <Muted style={{ fontSize: 16, textAlign: 'center' }}>{t('blitz.empty')}</Muted>
        </View>
      )}

      <Pressable style={[st.add, { bottom: Math.max(insets.bottom, 12) }]} onPress={() => router.push('/add-card')} hitSlop={10}>
        <Icon name="plus" size={18} color={colors.muted} />
        <Muted style={{ fontSize: 14 }}>{t('blitz.addCard')}</Muted>
      </Pressable>

      <TopicFilterSheet visible={filterOpen} value={filter} onClose={() => setFilterOpen(false)} onApply={(f) => { setFilter(f); setFilterOpen(false); }} />
    </Screen>
  );
}

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
      const list = await collections(db);
      setTopics(await Promise.all(list.map(async (c) => ({ uuid: c.uuid, name: c.name, due: await countDue(db, now, { topics: [c.uuid], noTopic: false }) }))));
      setNoTopicDue(await countDue(db, now, { topics: [], noTopic: true }));
      setPicked(new Set(value?.topics ?? []));
      setNoTopic(value?.noTopic ?? false);
    })();
  }, [visible, db, value]);

  const row = (key: string, name: string, due: number, on: boolean, toggle: () => void) => (
    <Pressable key={key} onPress={toggle} style={[st.checkRow, { borderBottomColor: colors.line }]}>
      <View style={[st.box, on ? { backgroundColor: colors.fg, borderColor: colors.fg } : { borderColor: colors.muted }]}>
        {on ? <Icon name="check" size={14} color={colors.bg} /> : null}
      </View>
      <Text style={{ flex: 1, color: colors.fg, fontSize: 16 }}>{name}</Text>
      <Muted style={{ fontSize: 13 }}>{due}</Muted>
    </Pressable>
  );

  const apply = () => onApply(picked.size || noTopic ? { topics: [...picked], noTopic } : null);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={[st.dim, { backgroundColor: colors.dim }]} onPress={onClose} />
      <View style={[st.sheet, { backgroundColor: colors.bg }]}>
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
        <Pill title={t('blitz.show')} onPress={apply} style={{ marginTop: 18 }} />
      </View>
    </Modal>
  );
}

const st = StyleSheet.create({
  filterRow: { alignItems: 'center', marginTop: -4 },
  cardArea: { flex: 1, paddingHorizontal: 24, paddingTop: 20, paddingBottom: 12 },
  card: { flex: 1, borderWidth: 1, borderRadius: 32, overflow: 'hidden', elevation: 2, shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 20, shadowOffset: { width: 0, height: 8 } },
  cardInner: { flex: 1, paddingHorizontal: 28, paddingTop: 22, paddingBottom: 22, alignItems: 'center' },
  face: { fontSize: 12, fontWeight: '600', letterSpacing: 1 },
  textWrap: { flexGrow: 1, justifyContent: 'center', paddingVertical: 16 },
  text: { fontSize: 24, fontWeight: '600', textAlign: 'center', lineHeight: 32 },
  hint: { fontSize: 13 },
  stamp: { position: 'absolute', top: 22, borderWidth: 2, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 3, fontWeight: '700', fontSize: 14 },
  stampRight: { left: 22, transform: [{ rotate: '-8deg' }] },
  stampWrong: { right: 22, transform: [{ rotate: '8deg' }] },
  bottom: { flexDirection: 'row', gap: 12, paddingHorizontal: 24, paddingBottom: 56 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 40, paddingBottom: 80 },
  big: { fontSize: 120, fontWeight: '600', letterSpacing: -6, lineHeight: 130 },
  add: { position: 'absolute', right: 24, flexDirection: 'row', alignItems: 'center', gap: 6 },
  dim: { flex: 1 },
  sheet: { borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingHorizontal: 24, paddingTop: 22, paddingBottom: 36 },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth },
  box: { width: 22, height: 22, borderRadius: 7, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
});
