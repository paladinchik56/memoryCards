/** An author and all their public topics (online). */
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';

import { Muted, Row, Screen, TopBar } from '@/components/ui';
import type { LibraryTopic } from '@/lib/api';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function Author() {
  const { nickname } = useLocalSearchParams<{ nickname: string }>();
  const { colors, t } = useSettings();
  const { api } = useSession();
  const [data, setData] = useState<{ nickname: string; topics: LibraryTopic[] } | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => { api?.author(nickname).then(setData).catch(() => setFailed(true)); }, [api, nickname]);

  return (
    <Screen>
      <TopBar left="chevron-left" onLeft={() => router.back()} />
      {failed ? <Muted style={{ textAlign: 'center', marginTop: 40 }}>{t('lib.offline')}</Muted> : !data ? <ActivityIndicator style={{ marginTop: 40 }} /> : (
        <FlatList
          data={data.topics}
          keyExtractor={(tp) => tp.share_token}
          contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 40 }}
          ListHeaderComponent={
            <View style={{ alignItems: 'center', paddingVertical: 12 }}>
              <View style={[st.avatar, { backgroundColor: colors.soft }]}>
                <Text style={{ fontSize: 30, fontWeight: '700', color: colors.muted }}>{data.nickname.slice(0, 1).toUpperCase()}</Text>
              </View>
              <Text style={{ fontSize: 22, fontWeight: '700', color: colors.fg, marginTop: 12 }}>{data.nickname}</Text>
              <Muted style={{ fontSize: 14, marginTop: 4 }}>{t('lib.authorTopics', { n: data.topics.length })}</Muted>
            </View>
          }
          renderItem={({ item }) => (
            <Row title={item.name} subtitle={t('lib.cardsN', { n: item.card_count })} onPress={() => router.push(`/library/shared/${item.share_token}`)} />
          )}
        />
      )}
    </Screen>
  );
}

const st = StyleSheet.create({ avatar: { width: 84, height: 84, borderRadius: 42, alignItems: 'center', justifyContent: 'center' } });
