/** All cards in the blitz: topic, question, answer, time until the next review. */
import { router, useFocusEffect } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useState } from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';

import { Muted, Screen, TopBar } from '@/components/ui';
import { blitzCards, type Card } from '@/lib/db';
import { formatDuration } from '@/lib/i18n';
import { useSettings } from '@/lib/settings';

export default function Cards() {
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const [cards, setCards] = useState<(Card & { topic: string | null })[]>([]);

  useFocusEffect(useCallback(() => { void blitzCards(db).then(setCards); }, [db]));

  const now = Date.now();
  return (
    <Screen>
      <TopBar left="chevron-left" onLeft={() => router.back()} title={t('cards.title')} />
      <FlatList
        data={cards}
        keyExtractor={(c) => c.uuid}
        contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 40 }}
        ListEmptyComponent={<Muted style={{ textAlign: 'center', marginTop: 40 }}>{t('cards.empty')}</Muted>}
        renderItem={({ item }) => (
          <View style={[st.row, { borderBottomColor: colors.line }]}>
            <View style={{ flex: 1 }}>
              <Muted style={st.topic}>{item.topic ?? t('lib.noTopic')}</Muted>
              <Text style={[st.q, { color: colors.fg }]}>{item.question}</Text>
              <Muted style={st.a}>{item.answer}</Muted>
            </View>
            <Muted style={st.when}>{item.next_review_at <= now ? t('cards.now') : formatDuration(item.next_review_at - now, t)}</Muted>
          </View>
        )}
      />
    </Screen>
  );
}

const st = StyleSheet.create({
  row: { flexDirection: 'row', gap: 12, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth },
  topic: { fontSize: 12, marginBottom: 3 },
  q: { fontSize: 16, fontWeight: '500' },
  a: { fontSize: 14, marginTop: 3 },
  when: { fontSize: 13 },
});
