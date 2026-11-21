/**
 * One of the user's own topics (or "No topic"), from the local database.
 * "Edit deck" selects cards for: to blitz, copy, move, out of the deck
 * (in "No topic": delete instead, there is no deck to take them out of).
 */
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useState } from 'react';
import { Alert, Pressable, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useBlitzAdder } from '@/components/blitz-adder';
import { ActionBar, QATable } from '@/components/qa';
import { ChoiceSheet } from '@/components/sheet';
import { Icon, Muted, Pill, Screen, TopBar } from '@/components/ui';
import {
  collections, copyCards, deleteCards, getCollection, moveCards, parseTags, topicCards, type Card, type Collection,
} from '@/lib/db';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function Topic() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const { revision, scheduleSync } = useSession();
  const insets = useSafeAreaInsets();
  const isNone = id === 'none';
  const [topic, setTopic] = useState<Collection | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [own, setOwn] = useState<Collection[]>([]);
  const [selected, setSelected] = useState<Set<string> | null>(null);
  const [target, setTarget] = useState<'copy' | 'move' | null>(null);

  const load = useCallback(async () => {
    if (!isNone) setTopic(await getCollection(db, id));
    setCards(await topicCards(db, isNone ? null : id));
    setOwn(await collections(db));
  }, [db, id, isNone]);
  useFocusEffect(useCallback(() => { void load(); }, [load, revision]));

  const done = () => { setSelected(null); scheduleSync(); void load(); };
  const adder = useBlitzAdder(done);
  const picked = [...(selected ?? [])];

  const toggle = (uuid: string) => {
    const n = new Set(selected);
    if (n.has(uuid)) n.delete(uuid); else n.add(uuid);
    setSelected(n);
  };

  const removeOrDelete = () => {
    if (!isNone) return void moveCards(db, picked, null).then(done);
    Alert.alert(t('lib.delete'), t('lib.deleteConfirm', { n: picked.length }), [
      { text: t('common.cancel'), style: 'cancel' },
      { text: t('lib.delete'), style: 'destructive', onPress: () => void deleteCards(db, picked).then(done) },
    ]);
  };

  const otherTopics = own.filter((c) => c.uuid !== id);
  const targets = target === 'move' && !isNone
    ? [...otherTopics.map((c) => ({ label: c.name, value: c.uuid as string | null })), { label: t('lib.noTopic'), value: null }]
    : otherTopics.map((c) => ({ label: c.name, value: c.uuid as string | null }));
  const startTarget = (kind: 'copy' | 'move') => (targets.length || kind === 'move' ? setTarget(kind) : Alert.alert(t('lib.noOwnTopics')));

  return (
    <Screen>
      {selected ? (
        <TopBar
          left="x" onLeft={() => setSelected(null)} title={t('lib.selectedN', { n: selected.size })}
          right={<Pressable onPress={() => setSelected(new Set(cards.map((c) => c.uuid)))}><Muted style={{ fontWeight: '600', color: colors.fg }}>{t('lib.all')}</Muted></Pressable>}
        />
      ) : (
        <TopBar
          left="chevron-left" onLeft={() => router.back()}
          right={isNone ? null : (
            <Pressable onPress={() => router.push({ pathname: '/topic-edit', params: { id } })} hitSlop={10}>
              <Muted style={{ fontWeight: '600', color: colors.fg }}>{t('lib.edit')}</Muted>
            </Pressable>
          )}
        />
      )}
      <QATable
        title={isNone ? t('lib.noTopic') : topic?.name ?? ''}
        description={topic?.description}
        tags={topic ? parseTags(topic.tags) : []}
        meta={[t('lib.cardsN', { n: cards.length }), topic ? t(`topic.${topic.visibility}` as 'topic.private') : ''].filter(Boolean).join(' · ')}
        cards={cards.map((c) => ({ ...c, inBlitz: !!c.in_pool }))}
        selected={selected ?? undefined}
        onToggle={toggle}
        onPressCard={(c) => router.push(`/card/${c.uuid}`)}
        header={selected || !cards.length ? null : (
          <Pill title={t('lib.editDeck')} onPress={() => setSelected(new Set())} style={{ marginTop: 16, paddingVertical: 14 }} />
        )}
        bottomPadding={selected ? 110 : 48}
      />
      {selected ? (
        <View style={{ paddingBottom: insets.bottom }}>
          <ActionBar actions={[
            { label: t('lib.toBlitz'), icon: <Icon name="zap" />, disabled: !picked.length, onPress: () => void adder.addOwn(picked) },
            { label: t('lib.copy'), icon: <Icon name="copy" />, disabled: !picked.length, onPress: () => startTarget('copy') },
            { label: t('lib.move'), icon: <Icon name="arrow-right" />, disabled: !picked.length, onPress: () => startTarget('move') },
            isNone
              ? { label: t('lib.delete'), icon: <Icon name="trash-2" />, disabled: !picked.length, onPress: removeOrDelete }
              : { label: t('lib.fromDeck'), icon: <Icon name="minus" />, disabled: !picked.length, onPress: removeOrDelete },
          ]} />
        </View>
      ) : null}
      <ChoiceSheet
        visible={!!target} title={target === 'copy' ? t('lib.copyTo') : t('lib.moveTo')} onClose={() => setTarget(null)}
        choices={targets}
        onPick={(to) => {
          if (target === 'copy' && to) void copyCards(db, picked, to).then(done);
          if (target === 'move') void moveCards(db, picked, to).then(done);
        }}
      />
      {adder.sheet}
    </Screen>
  );
}
