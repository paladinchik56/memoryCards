/**
 * Topic page body: title, description, tags and a question | answer list.
 * With `selected` set the rows become checkboxes (deck editing / picking).
 */
import type { ReactNode } from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';

import { Checkbox } from './sheet';
import { Muted, Title } from './ui';
import { mathToPlain } from '@/lib/math';
import { useSettings } from '@/lib/settings';

export type QACard = { uuid: string; question: string; answer: string; inBlitz?: boolean };

export function Tags({ tags }: { tags: string[] }) {
  const { colors } = useSettings();
  if (!tags.length) return null;
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
      {tags.map((tag) => (
        <Text key={tag} style={[st.tag, { color: colors.muted, borderColor: colors.line }]}>{tag}</Text>
      ))}
    </View>
  );
}

export function QATable({ title, description, tags = [], meta, cards, header, selected, onToggle, onPressCard, bottomPadding = 48 }: {
  title: string; description?: string; tags?: string[]; meta?: ReactNode; cards: QACard[]; header?: ReactNode;
  selected?: Set<string>; onToggle?: (uuid: string) => void; onPressCard?: (card: QACard) => void; bottomPadding?: number;
}) {
  const { colors, t } = useSettings();
  const selecting = !!selected;
  return (
    <FlatList
      data={cards}
      keyExtractor={(c) => c.uuid}
      contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: bottomPadding }}
      ListHeaderComponent={
        <View>
          <Title style={{ fontSize: 28 }}>{title}</Title>
          {description ? <Text style={[st.desc, { color: colors.fg }]}>{description}</Text> : null}
          <Tags tags={tags} />
          {meta ? <Muted style={{ fontSize: 14, marginTop: 8 }}>{meta}</Muted> : null}
          {header}
          <View style={[st.row, { borderBottomColor: colors.line, marginTop: 18 }]}>
            {selecting ? <View style={{ width: 22 }} /> : null}
            <Muted style={st.headCell}>{t('lib.questionCol').toUpperCase()}</Muted>
            <Muted style={st.headCell}>{t('lib.answerCol').toUpperCase()}</Muted>
          </View>
        </View>
      }
      ListEmptyComponent={<Muted style={{ marginTop: 24 }}>{t('lib.emptyTopic')}</Muted>}
      renderItem={({ item }) => (
        <Pressable
          onPress={() => (selecting ? onToggle?.(item.uuid) : onPressCard?.(item))}
          disabled={!selecting && !onPressCard}
          style={({ pressed }) => [st.row, { borderBottomColor: colors.line, opacity: pressed ? 0.6 : 1 }]}
        >
          {selecting ? <Checkbox on={selected.has(item.uuid)} /> : null}
          <View style={{ flex: 1 }}>
            <Text style={[st.cell, { color: colors.fg }]}>{mathToPlain(item.question)}</Text>
            {item.inBlitz ? <Muted style={{ fontSize: 11, marginTop: 3 }}>● {t('lib.inBlitzMark')}</Muted> : null}
          </View>
          <Text style={[st.cell, { color: colors.muted }]}>{mathToPlain(item.answer)}</Text>
        </Pressable>
      )}
    />
  );
}

/** Bottom action bar for selection mode. */
export function ActionBar({ actions }: { actions: { label: string; icon: ReactNode; onPress: () => void; disabled?: boolean }[] }) {
  const { colors } = useSettings();
  return (
    <View style={[st.bar, { borderTopColor: colors.line, backgroundColor: colors.bg }]}>
      {actions.map((a) => (
        <Pressable key={a.label} onPress={a.onPress} disabled={a.disabled} style={[st.barItem, { opacity: a.disabled ? 0.35 : 1 }]}>
          {a.icon}
          <Text style={{ fontSize: 12, fontWeight: '500', color: colors.fg }}>{a.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

const st = StyleSheet.create({
  desc: { fontSize: 15, marginTop: 8, opacity: 0.8, lineHeight: 21 },
  tag: { fontSize: 12, borderWidth: 1, borderRadius: 999, paddingHorizontal: 9, paddingVertical: 3 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 13, borderBottomWidth: StyleSheet.hairlineWidth },
  headCell: { flex: 1, fontSize: 12, fontWeight: '600', letterSpacing: 0.8 },
  cell: { flex: 1, fontSize: 15, lineHeight: 20 },
  bar: { flexDirection: 'row', borderTopWidth: StyleSheet.hairlineWidth, paddingTop: 10, paddingBottom: 6 },
  barItem: { flex: 1, alignItems: 'center', gap: 6 },
});
