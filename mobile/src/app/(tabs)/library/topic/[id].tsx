/** One of the user's own topics (or "No topic"), read from the local database. */
import { router, useLocalSearchParams } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useEffect, useState } from 'react';

import { QATable } from '@/components/qa';
import { Screen, TopBar } from '@/components/ui';
import { topicCards, type Card, type Collection } from '@/lib/db';
import { useSettings } from '@/lib/settings';

export default function Topic() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const db = useSQLiteContext();
  const { t } = useSettings();
  const [topic, setTopic] = useState<Collection | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const isNone = id === 'none';

  useEffect(() => {
    (async () => {
      if (!isNone) setTopic(await db.getFirstAsync<Collection>('SELECT * FROM collections WHERE uuid = ?', id));
      setCards(await topicCards(db, isNone ? null : id));
    })();
  }, [db, id, isNone]);

  return (
    <Screen>
      <TopBar left="chevron-left" onLeft={() => router.back()} />
      <QATable
        title={isNone ? t('lib.noTopic') : topic?.name ?? ''}
        description={topic?.description}
        meta={t('lib.cardsN', { n: cards.length })}
        cards={cards}
      />
    </Screen>
  );
}
