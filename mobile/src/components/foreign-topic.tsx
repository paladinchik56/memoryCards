/**
 * Someone else's topic (an added topic, or one from the shared library):
 * read-only cards; pick cards to put into the blitz or copy into an own
 * topic; add / remove the topic; open the author's page.
 */
import { router } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useEffect, useState } from 'react';
import { Alert, Pressable, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useBlitzAdder } from './blitz-adder';
import { ActionBar, QATable, type QACard } from './qa';
import { ChoiceSheet } from './sheet';
import { Icon, Muted, Pill, Screen, TopBar } from './ui';
import { collections, type Collection } from '@/lib/db';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export type ForeignTopicData = {
  share_token: string; name: string; description: string; tags: string[]; owner: string;
  is_added: boolean; is_owner?: boolean; cards: QACard[];
};

export function ForeignTopic({ topic, onChanged }: { topic: ForeignTopicData; onChanged?: () => void }) {
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const { api, syncNow } = useSession();
  const insets = useSafeAreaInsets();
  const [selected, setSelected] = useState<Set<string> | null>(null);
  const [isAdded, setIsAdded] = useState(topic.is_added);
  const [busy, setBusy] = useState(false);
  const [copyOf, setCopyOf] = useState<string[] | null>(null);
  const [cardMenu, setCardMenu] = useState<QACard | null>(null);
  const [own, setOwn] = useState<Collection[]>([]);
  const adder = useBlitzAdder(() => { setSelected(null); onChanged?.(); });

  useEffect(() => { setIsAdded(topic.is_added); }, [topic.is_added]);
  useEffect(() => { void collections(db).then(setOwn); }, [db]);

  const toggleAdded = async () => {
    if (!api) return;
    setBusy(true);
    try {
      const res = await api.subscribe(topic.share_token, !isAdded);
      setIsAdded(res.is_added);
      await syncNow();
      onChanged?.();
    } catch {
      Alert.alert(t('lib.needNetwork'));
    } finally {
      setBusy(false);
    }
  };

  const copy = async (uuids: string[], target: string) => {
    if (!api) return;
    try {
      const res = await api.copy(topic.share_token, uuids, target);
      await syncNow();
      Alert.alert(t('lib.copied', { n: res.copied }));
      setSelected(null);
    } catch {
      Alert.alert(t('lib.needNetwork'));
    }
  };
  const startCopy = (uuids: string[]) => (own.length ? setCopyOf(uuids) : Alert.alert(t('lib.noOwnTopics')));

  const toggle = (uuid: string) => {
    const n = new Set(selected);
    if (n.has(uuid)) n.delete(uuid); else n.add(uuid);
    setSelected(n);
  };
  const picked = [...(selected ?? [])];

  const header = selected ? null : (
    <View style={{ flexDirection: 'row', gap: 10, marginTop: 16 }}>
      {topic.is_owner ? null : (
        <Pill title={isAdded ? t('lib.removeTopic') : t('lib.addTopic')} ghost={isAdded} onPress={toggleAdded} loading={busy} style={{ flex: 1, paddingVertical: 14 }} />
      )}
      <Pill title={t('lib.select')} ghost onPress={() => setSelected(new Set())} style={{ paddingVertical: 14, paddingHorizontal: 22 }} />
    </View>
  );

  return (
    <Screen>
      {selected ? (
        <TopBar
          left="x" onLeft={() => setSelected(null)} title={t('lib.selectedN', { n: selected.size })}
          right={<Pressable onPress={() => setSelected(new Set(topic.cards.map((c) => c.uuid)))}><Muted style={{ fontWeight: '600', color: colors.fg }}>{t('lib.all')}</Muted></Pressable>}
        />
      ) : (
        <TopBar left="chevron-left" onLeft={() => router.back()} />
      )}
      <QATable
        title={topic.name}
        description={topic.description}
        tags={topic.tags}
        meta={t('lib.cardsN', { n: topic.cards.length })}
        header={
          <>
            <Pressable onPress={() => router.push(`/library/author/${encodeURIComponent(topic.owner)}`)} hitSlop={6} style={{ marginTop: 6 }}>
              <Muted style={{ fontSize: 13 }}>{t('lib.by', { name: topic.owner })} ›</Muted>
            </Pressable>
            {header}
          </>
        }
        cards={topic.cards}
        selected={selected ?? undefined}
        onToggle={toggle}
        onPressCard={(c) => setCardMenu(c)}
        bottomPadding={selected ? 110 : 48}
      />
      {selected ? (
        <View style={{ paddingBottom: insets.bottom }}>
          <ActionBar actions={[
            { label: t('lib.toBlitz'), icon: <Icon name="zap" />, disabled: !picked.length, onPress: () => void adder.addForeign(topic.share_token, picked) },
            { label: t('lib.copy'), icon: <Icon name="copy" />, disabled: !picked.length, onPress: () => startCopy(picked) },
          ]} />
        </View>
      ) : null}

      <ChoiceSheet
        visible={!!cardMenu} title={cardMenu?.question ?? ''} onClose={() => setCardMenu(null)}
        choices={[{ label: t('card.addToBlitz'), value: 'blitz' }, { label: t('lib.copyTo'), value: 'copy' }]}
        onPick={(v) => {
          const c = cardMenu;
          if (!c) return;
          if (v === 'blitz') void adder.addForeign(topic.share_token, [c.uuid]);
          else startCopy([c.uuid]);
        }}
      />
      <ChoiceSheet
        visible={!!copyOf} title={t('lib.copyTo')} onClose={() => setCopyOf(null)}
        choices={own.map((c) => ({ label: c.name, value: c.uuid }))}
        onPick={(target) => { const u = copyOf; if (u) void copy(u, target); }}
      />
      {adder.sheet}
    </Screen>
  );
}
