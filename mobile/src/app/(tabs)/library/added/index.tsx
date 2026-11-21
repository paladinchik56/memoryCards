/** Topics of other users the user added to themselves (stored locally, read-only). */
import { router, useFocusEffect } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useState } from 'react';
import { ScrollView } from 'react-native';

import { Muted, Row, Screen, TopBar } from '@/components/ui';
import { addedTopics, type AddedTopic } from '@/lib/db';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function AddedTopics() {
  const db = useSQLiteContext();
  const { t } = useSettings();
  const { revision } = useSession();
  const [list, setList] = useState<(AddedTopic & { count: number })[]>([]);

  useFocusEffect(useCallback(() => { void addedTopics(db).then(setList); }, [db, revision]));

  return (
    <Screen>
      <TopBar left="chevron-left" onLeft={() => router.back()} title={t('lib.added')} />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 40 }}>
        {list.length ? list.map((tp) => (
          <Row
            key={tp.uuid} title={tp.name}
            subtitle={`${t('lib.by', { name: tp.owner })} · ${t('lib.cardsN', { n: tp.count })}`}
            onPress={() => router.push(`/library/added/${tp.uuid}`)}
          />
        )) : <Muted style={{ marginTop: 16, lineHeight: 22 }}>{t('lib.noAdded')}</Muted>}
      </ScrollView>
    </Screen>
  );
}
