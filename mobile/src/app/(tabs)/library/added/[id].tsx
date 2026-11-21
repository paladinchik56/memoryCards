/** An added topic, from the local copy (works offline; actions need the server). */
import { router, useLocalSearchParams } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useEffect, useState } from 'react';

import { ForeignTopic, type ForeignTopicData } from '@/components/foreign-topic';
import { Screen, TopBar } from '@/components/ui';
import { addedCards, getAddedTopic, parseTags } from '@/lib/db';
import { useSession } from '@/lib/session';

export default function AddedTopic() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const db = useSQLiteContext();
  const { revision } = useSession();
  const [topic, setTopic] = useState<ForeignTopicData | null>(null);

  const load = useCallback(async () => {
    const tp = await getAddedTopic(db, id);
    if (!tp) return router.back(); // removed from added topics
    setTopic({ ...tp, tags: parseTags(tp.tags), is_added: true, cards: await addedCards(db, id) });
  }, [db, id]);
  useEffect(() => { void load(); }, [load, revision]);

  if (!topic) return <Screen><TopBar left="chevron-left" onLeft={() => router.back()} /></Screen>;
  return <ForeignTopic topic={topic} onChanged={() => void load()} />;
}
