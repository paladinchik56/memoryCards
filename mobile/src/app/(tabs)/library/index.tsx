import { router, useFocusEffect } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useState } from 'react';
import { View } from 'react-native';

import { Row, Screen, Title } from '@/components/ui';
import { addedTopics, collections } from '@/lib/db';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function Library() {
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const { revision } = useSession();
  const [mine, setMine] = useState(0);
  const [added, setAdded] = useState(0);

  useFocusEffect(useCallback(() => {
    void collections(db).then((c) => setMine(c.length));
    void addedTopics(db).then((a) => setAdded(a.length));
  }, [db, revision]));

  return (
    <Screen>
      <View style={{ paddingHorizontal: 24, paddingTop: 28 }}>
        <Title style={{ fontSize: 34 }}>{t('lib.title')}</Title>
        <View style={{ marginTop: 28, borderTopWidth: 1, borderTopColor: colors.line }}>
          <Row title={t('lib.mine')} subtitle={t('lib.topicsN', { n: mine })} onPress={() => router.push('/library/mine')} />
          <Row title={t('lib.added')} subtitle={t('lib.topicsN', { n: added })} onPress={() => router.push('/library/added')} />
          <Row title={t('lib.browse')} subtitle={t('lib.browseHint')} onPress={() => router.push('/library/browse')} />
        </View>
      </View>
    </Screen>
  );
}
