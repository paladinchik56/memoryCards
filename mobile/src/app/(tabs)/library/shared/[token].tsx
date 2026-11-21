/** A topic from the shared library (online). */
import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator } from 'react-native';

import { ForeignTopic } from '@/components/foreign-topic';
import { Muted, Screen, TopBar } from '@/components/ui';
import type { SharedTopic } from '@/lib/api';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function Shared() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { t } = useSettings();
  const { api } = useSession();
  const [topic, setTopic] = useState<SharedTopic | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    api?.shared(token).then(setTopic).catch(() => setFailed(true));
  }, [api, token]);
  useEffect(load, [load]);

  if (!topic) {
    return (
      <Screen>
        <TopBar left="chevron-left" onLeft={() => router.back()} />
        {!api ? <Muted style={{ textAlign: 'center', marginTop: 40 }}>{t('guest.needAccount')}</Muted> : failed ? <Muted style={{ textAlign: 'center', marginTop: 40 }}>{t('lib.offline')}</Muted> : <ActivityIndicator style={{ marginTop: 40 }} />}
      </Screen>
    );
  }
  return (
    <ForeignTopic
      topic={{ ...topic, cards: topic.cards.map((c) => ({ ...c, inBlitz: c.in_blitz })) }}
      onChanged={load}
    />
  );
}
