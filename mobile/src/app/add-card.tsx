/**
 * Add a card. It goes straight into the blitz. The form stays open after
 * adding and remembers the chosen topic, so many cards can be added in a row.
 */
import { router } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useEffect, useRef, useState, type ComponentRef } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { ChoiceSheet } from '@/components/sheet';
import { Chip, Muted, Pill, Screen, TopBar } from '@/components/ui';
import { addCard, collections, DuplicateQuestion, getMeta, setMeta, type Collection } from '@/lib/db';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function AddCard() {
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const { scheduleSync } = useSession();
  const [topics, setTopics] = useState<Collection[]>([]);
  const [topic, setTopic] = useState<string | null>(null);
  const [question, setQuestion] = useState('');
  const [answerText, setAnswerText] = useState('');
  const [note, setNote] = useState<string | null>(null);
  const questionRef = useRef<ComponentRef<typeof TextInput>>(null);

  useEffect(() => {
    (async () => {
      const list = await collections(db);
      setTopics(list);
      const last = await getMeta(db, 'last_topic');
      if (last && list.some((c) => c.uuid === last)) setTopic(last);
    })();
  }, [db]);

  const [choosing, setChoosing] = useState(false);
  const pick = (uuid: string | null) => {
    setTopic(uuid);
    void setMeta(db, 'last_topic', uuid);
  };

  const submit = async () => {
    if (!question.trim() || !answerText.trim()) return setNote(t('add.empty'));
    try {
      await addCard(db, question, answerText, topic);
      scheduleSync();
      setQuestion('');
      setAnswerText('');
      setNote(t('add.added'));
      questionRef.current?.focus();
    } catch (e) {
      setNote(e instanceof DuplicateQuestion ? t('add.duplicate') : String(e));
    }
  };

  const topicName = topics.find((c) => c.uuid === topic)?.name ?? t('add.noTopic');
  const field = [st.field, { borderColor: colors.line, color: colors.fg }];
  return (
    <Screen edges={['top', 'bottom']}>
      <TopBar left="x" onLeft={() => router.back()} title={t('add.title')} />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={st.wrap} keyboardShouldPersistTaps="handled">
          <Chip title={topicName} icon="folder" active={!!topic} onPress={() => setChoosing(true)} />
          <View style={{ gap: 12, marginTop: 18 }}>
            <TextInput
              ref={questionRef} style={field} value={question} onChangeText={(v) => { setQuestion(v); setNote(null); }}
              placeholder={t('add.question')} placeholderTextColor={colors.muted} multiline autoFocus
            />
            <TextInput
              style={field} value={answerText} onChangeText={(v) => { setAnswerText(v); setNote(null); }}
              placeholder={t('add.answer')} placeholderTextColor={colors.muted} multiline
            />
          </View>
          <Pill title={t('add.submit')} onPress={submit} style={{ marginTop: 20 }} />
          {note ? <Text style={[st.note, { color: colors.fg }]}>{note}</Text> : <Muted style={st.note}> </Muted>}
        </ScrollView>
      </KeyboardAvoidingView>
      <ChoiceSheet<string | null>
        visible={choosing} title={t('add.chooseTopic')} selected={topic} onClose={() => setChoosing(false)}
        choices={[{ label: t('add.noTopic'), value: null }, ...topics.map((c) => ({ label: c.name, value: c.uuid as string | null }))]}
        onPick={pick}
      />
    </Screen>
  );
}

const st = StyleSheet.create({
  wrap: { paddingHorizontal: 24, paddingTop: 8, paddingBottom: 40 },
  field: { borderWidth: 1, borderRadius: 18, paddingHorizontal: 16, paddingTop: 14, paddingBottom: 14, fontSize: 17, minHeight: 92, textAlignVertical: 'top' },
  note: { marginTop: 16, textAlign: 'center', fontSize: 14, fontWeight: '500' },
});
