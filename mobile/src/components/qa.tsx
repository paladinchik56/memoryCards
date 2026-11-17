/** Topic page body: title, description and a question | answer list. */
import type { ReactNode } from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';

import { Muted, Title } from './ui';
import { useSettings } from '@/lib/settings';

export function QATable({ title, description, meta, cards, header }: {
  title: string; description?: string; meta?: string; cards: { uuid: string; question: string; answer: string }[]; header?: ReactNode;
}) {
  const { colors, t } = useSettings();
  return (
    <FlatList
      data={cards}
      keyExtractor={(c) => c.uuid}
      contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 48 }}
      ListHeaderComponent={
        <View>
          <Title style={{ fontSize: 28 }}>{title}</Title>
          {description ? <Text style={[st.desc, { color: colors.fg }]}>{description}</Text> : null}
          {meta ? <Muted style={{ fontSize: 14, marginTop: 6 }}>{meta}</Muted> : null}
          {header}
          <View style={[st.row, { borderBottomColor: colors.line, marginTop: 18 }]}>
            <Muted style={st.headCell}>{t('lib.questionCol').toUpperCase()}</Muted>
            <Muted style={st.headCell}>{t('lib.answerCol').toUpperCase()}</Muted>
          </View>
        </View>
      }
      ListEmptyComponent={<Muted style={{ marginTop: 24 }}>{t('lib.emptyTopic')}</Muted>}
      renderItem={({ item }) => (
        <View style={[st.row, { borderBottomColor: colors.line }]}>
          <Text style={[st.cell, { color: colors.fg }]}>{item.question}</Text>
          <Text style={[st.cell, { color: colors.muted }]}>{item.answer}</Text>
        </View>
      )}
    />
  );
}

const st = StyleSheet.create({
  desc: { fontSize: 15, marginTop: 8, opacity: 0.8, lineHeight: 21 },
  row: { flexDirection: 'row', gap: 14, paddingVertical: 13, borderBottomWidth: StyleSheet.hairlineWidth },
  headCell: { flex: 1, fontSize: 12, fontWeight: '600', letterSpacing: 0.8 },
  cell: { flex: 1, fontSize: 15, lineHeight: 20 },
});
