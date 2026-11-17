/** "How repetition works" — built from the same constants the scheduler uses. */
import { router } from 'expo-router';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { Muted, Screen, TopBar } from '@/components/ui';
import { formatDuration } from '@/lib/i18n';
import { MAX_STAGE, REQUIRED_CORRECT, STAGE_INTERVALS_S } from '@/lib/scheduler';
import { useSettings } from '@/lib/settings';

export default function Algorithm() {
  const { colors, t } = useSettings();
  return (
    <Screen>
      <TopBar left="chevron-left" onLeft={() => router.back()} title={t('algo.title')} />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 48 }}>
        <Text style={[st.p, { color: colors.fg }]}>{t('algo.intro')}</Text>
        <View style={[st.head, { borderBottomColor: colors.line }]}>
          <Muted style={st.c1}>{t('algo.stage')}</Muted>
          <Muted style={st.c2}>{t('algo.interval')}</Muted>
          <Muted style={st.c3}>{t('algo.need')}</Muted>
        </View>
        {STAGE_INTERVALS_S.map((sec, i) => (
          <View key={i} style={[st.row, { borderBottomColor: colors.line }]}>
            <Text style={[st.c1, st.cell, { color: colors.fg }]}>{i + 1}</Text>
            <Text style={[st.c2, st.cell, { color: colors.fg }]}>{formatDuration(sec * 1000, t)}</Text>
            <Text style={[st.c3, st.cell, { color: colors.fg }]}>{i < MAX_STAGE ? REQUIRED_CORRECT[i] : t('algo.max')}</Text>
          </View>
        ))}
        <Text style={[st.p, { color: colors.fg, marginTop: 24 }]}>{t('algo.rules')}</Text>
      </ScrollView>
    </Screen>
  );
}

const st = StyleSheet.create({
  p: { fontSize: 16, lineHeight: 24, marginTop: 8 },
  head: { flexDirection: 'row', marginTop: 24, paddingBottom: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  row: { flexDirection: 'row', paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth },
  cell: { fontSize: 16 },
  c1: { width: 70, fontSize: 13 },
  c2: { flex: 1, fontSize: 13 },
  c3: { width: 120, textAlign: 'right', fontSize: 13 },
});
