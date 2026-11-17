/** Public topics of all users (online). */
import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, TextInput, View } from 'react-native';

import { Icon, Muted, Row, Screen, TopBar } from '@/components/ui';
import type { LibraryTopic } from '@/lib/api';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function Browse() {
  const { colors, t } = useSettings();
  const { api } = useSession();
  const [topics, setTopics] = useState<LibraryTopic[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState('');

  useEffect(() => {
    api?.library().then(setTopics).catch(() => setFailed(true));
  }, [api]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!topics || !q) return topics ?? [];
    return topics.filter((tp) => `${tp.name} ${tp.description}`.toLowerCase().includes(q));
  }, [topics, query]);

  return (
    <Screen>
      <TopBar left="chevron-left" onLeft={() => router.back()} title={t('lib.browse')} />
      <View style={[st.search, { backgroundColor: colors.soft }]}>
        <Icon name="search" size={18} color={colors.muted} />
        <TextInput
          style={{ flex: 1, color: colors.fg, fontSize: 15 }} value={query} onChangeText={setQuery}
          placeholder={t('lib.search')} placeholderTextColor={colors.muted}
        />
      </View>
      {failed ? <Muted style={st.msg}>{t('lib.offline')}</Muted> : !topics ? <ActivityIndicator style={{ marginTop: 40 }} /> : (
        <FlatList
          data={shown}
          keyExtractor={(tp) => tp.share_token}
          contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 40 }}
          renderItem={({ item }) => (
            <Row
              title={item.name}
              subtitle={[t('lib.by', { name: item.owner }), item.description].filter(Boolean).join(' · ')}
              value={String(item.card_count)}
              onPress={() => router.push(`/library/shared/${item.share_token}`)}
            />
          )}
        />
      )}
    </Screen>
  );
}

const st = StyleSheet.create({
  search: { flexDirection: 'row', alignItems: 'center', gap: 10, marginHorizontal: 24, marginBottom: 6, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 11 },
  msg: { textAlign: 'center', marginTop: 40 },
});
