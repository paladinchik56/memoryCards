/** One own card: edit question/answer, add to blitz / reset progress, delete. */
import { router, useLocalSearchParams } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useEffect, useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput } from 'react-native';

import { Muted, Pill, Screen, TopBar } from '@/components/ui';
import { deleteCards, getCard, resetIntoPool, updateCard, type Card } from '@/lib/db';
import { formatDuration } from '@/lib/i18n';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function CardScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const { scheduleSync } = useSession();
  const [card, setCard] = useState<Card | null>(null);
  const [question, setQuestion] = useState('');
  const [answerText, setAnswerText] = useState('');
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    const c = await getCard(db, id);
    setCard(c);
    if (c) { setQuestion(c.question); setAnswerText(c.answer); }
  }, [db, id]);
  useEffect(() => { void load(); }, [load]);

  if (!card) return <Screen><TopBar left="x" onLeft={() => router.back()} /></Screen>;

  const changed = question.trim() !== card.question || answerText.trim() !== card.answer;
  const save = async () => {
    if (!question.trim() || !answerText.trim()) return setNote(t('add.empty'));
    await updateCard(db, card.uuid, question, answerText);
    scheduleSync();
    setNote(t('card.saved'));
    void load();
  };
  const toBlitz = () => {
    const go = async () => { await resetIntoPool(db, [card.uuid]); scheduleSync(); void load(); };
    if (!card.in_pool) return void go();
    Alert.alert(t('card.resetProgress'), t('card.resetConfirm'), [
      { text: t('common.cancel'), style: 'cancel' },
      { text: t('conflict.reset'), onPress: () => void go() },
    ]);
  };
  const remove = () => Alert.alert(t('card.delete'), t('card.deleteConfirm'), [
    { text: t('common.cancel'), style: 'cancel' },
    { text: t('lib.delete'), style: 'destructive', onPress: async () => { await deleteCards(db, [card.uuid]); scheduleSync(); router.back(); } },
  ]);

  const now = Date.now();
  const status = card.in_pool
    ? t('card.status', {
        stage: card.stage + 1,
        when: card.next_review_at <= now ? t('card.dueNow') : t('card.dueIn', { t: formatDuration(card.next_review_at - now, t) }),
      })
    : t('card.notInBlitz');
  const field = [st.field, { borderColor: colors.line, color: colors.fg }];

  return (
    <Screen edges={['top', 'bottom']}>
      <TopBar left="x" onLeft={() => router.back()} title={t('card.title')} />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 40, gap: 12 }} keyboardShouldPersistTaps="handled">
          <TextInput style={field} value={question} onChangeText={(v) => { setQuestion(v); setNote(null); }} placeholder={t('add.question')} placeholderTextColor={colors.muted} multiline />
          <TextInput style={field} value={answerText} onChangeText={(v) => { setAnswerText(v); setNote(null); }} placeholder={t('add.answer')} placeholderTextColor={colors.muted} multiline />
          <Muted style={{ fontSize: 14 }}>{status}</Muted>
          <Pill title={t('card.save')} onPress={save} disabled={!changed} style={{ marginTop: 8 }} />
          <Pill title={card.in_pool ? t('card.resetProgress') : t('card.addToBlitz')} ghost onPress={toBlitz} />
          {note ? <Text style={{ color: colors.fg, textAlign: 'center', fontWeight: '500' }}>{note}</Text> : null}
          <Pressable onPress={remove} style={{ alignItems: 'center', paddingVertical: 18 }}>
            <Text style={{ color: colors.fg, fontSize: 15, fontWeight: '500' }}>{t('card.delete')}</Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const st = StyleSheet.create({
  field: { borderWidth: 1, borderRadius: 18, paddingHorizontal: 16, paddingVertical: 14, fontSize: 17, minHeight: 92, textAlignVertical: 'top' },
});
