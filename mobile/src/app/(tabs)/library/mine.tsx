import { router, useFocusEffect } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useState } from 'react';
import { Pressable, ScrollView } from 'react-native';

import { Icon, Row, Screen, TopBar } from '@/components/ui';
import { collections, noTopicCount, type Collection } from '@/lib/db';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function MyTopics() {
  const db = useSQLiteContext();
  const { t } = useSettings();
  const { revision } = useSession();
  const [list, setList] = useState<(Collection & { count: number })[]>([]);
  const [none, setNone] = useState(0);

  useFocusEffect(useCallback(() => {
    void collections(db).then(setList);
    void noTopicCount(db).then(setNone);
  }, [db, revision]));

  return (
    <Screen>
      <TopBar
        left="chevron-left" onLeft={() => router.back()} title={t('lib.mine')}
        right={<Pressable onPress={() => router.push('/topic-edit')} hitSlop={10}><Icon name="plus" size={24} /></Pressable>}
      />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 40 }}>
        {list.map((c) => (
          <Row key={c.uuid} title={c.name} subtitle={t('lib.cardsN', { n: c.count })} onPress={() => router.push(`/library/topic/${c.uuid}`)} />
        ))}
        <Row title={t('lib.noTopic')} subtitle={t('lib.cardsN', { n: none })} onPress={() => router.push('/library/topic/none')} />
      </ScrollView>
    </Screen>
  );
}
