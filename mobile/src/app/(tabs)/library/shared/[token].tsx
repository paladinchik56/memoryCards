/** Someone's public topic: its cards, and "add to blitz" (copies them to you). */
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Alert } from 'react-native';

import { QATable } from '@/components/qa';
import { Muted, Pill, Screen, TopBar } from '@/components/ui';
import type { SharedTopic } from '@/lib/api';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function Shared() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { t } = useSettings();
  const { api, syncNow } = useSession();
  const [topic, setTopic] = useState<SharedTopic | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api?.shared(token).then(setTopic).catch(() => setFailed(true));
  }, [api, token]);

  const addAll = async () => {
    if (!api || !topic) return;
    setBusy(true);
    try {
      const res = await api.take(token, 'new');
      await syncNow();
      Alert.alert(topic.name, t('lib.addedResult', { added: res.added, skipped: res.skipped }));
    } catch {
      Alert.alert(t('lib.offline'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <TopBar left="chevron-left" onLeft={() => router.back()} />
      {failed ? <Muted style={{ textAlign: 'center', marginTop: 40 }}>{t('lib.offline')}</Muted> : !topic ? <ActivityIndicator style={{ marginTop: 40 }} /> : (
        <QATable
          title={topic.name}
          description={topic.description}
          meta={`${t('lib.by', { name: topic.owner })} · ${t('lib.cardsN', { n: topic.cards.length })}`}
          cards={topic.cards}
          header={topic.is_owner
            ? <Muted style={{ marginTop: 16 }}>{t('lib.yours')}</Muted>
            : <Pill title={t('lib.addToBlitz', { n: topic.cards.length })} onPress={addAll} loading={busy} style={{ marginTop: 18 }} />}
        />
      )}
    </Screen>
  );
}
