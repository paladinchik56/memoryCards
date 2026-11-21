/** Create a topic, or edit one (?id=): name, description, tags, access. */
import { router, useLocalSearchParams } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { Muted, Pill, Screen, TopBar } from '@/components/ui';
import { getCollection, parseTags, saveCollection } from '@/lib/db';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

const VISIBILITIES = ['private', 'unlisted', 'public'] as const;

export default function TopicEdit() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const { scheduleSync } = useSession();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [visibility, setVisibility] = useState<string>('private');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    void getCollection(db, id).then((c) => {
      if (!c) return;
      setName(c.name);
      setDescription(c.description);
      setTags(parseTags(c.tags).join(', '));
      setVisibility(c.visibility);
    });
  }, [db, id]);

  const save = async () => {
    if (!name.trim()) return setError(t('topic.nameRequired'));
    const tagList = [...new Set(tags.split(',').map((s) => s.trim().slice(0, 30)).filter(Boolean))].slice(0, 10);
    const uuid = await saveCollection(db, id ?? null, { name: name.slice(0, 100), description: description.slice(0, 700), tags: tagList, visibility });
    scheduleSync();
    if (id) router.back();
    else router.replace(`/library/topic/${uuid}`);
  };

  const input = [st.input, { color: colors.fg, borderColor: colors.line }];
  return (
    <Screen edges={['top', 'bottom']}>
      <TopBar left="x" onLeft={() => router.back()} title={id ? t('lib.editTopic') : t('lib.newTopic')} />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 40, gap: 12 }} keyboardShouldPersistTaps="handled">
          <TextInput style={input} value={name} onChangeText={(v) => { setName(v); setError(null); }} placeholder={t('topic.name')} placeholderTextColor={colors.muted} autoFocus={!id} />
          <TextInput style={[input, { minHeight: 90, textAlignVertical: 'top' }]} value={description} onChangeText={setDescription} placeholder={t('topic.description')} placeholderTextColor={colors.muted} multiline />
          <TextInput style={input} value={tags} onChangeText={setTags} placeholder={t('topic.tags')} placeholderTextColor={colors.muted} autoCapitalize="none" />
          <Muted style={{ fontSize: 13, marginTop: 8 }}>{t('topic.visibility')}</Muted>
          <View style={[st.seg, { backgroundColor: colors.soft }]}>
            {VISIBILITIES.map((v) => (
              <Pressable key={v} onPress={() => setVisibility(v)} style={[st.segItem, visibility === v && { backgroundColor: colors.bg }]}>
                <Text style={{ fontSize: 14, fontWeight: '500', color: visibility === v ? colors.fg : colors.muted }}>{t(`topic.${v}`)}</Text>
              </Pressable>
            ))}
          </View>
          {error ? <Text style={{ color: colors.fg, fontWeight: '500' }}>{error}</Text> : null}
          <Pill title={t('topic.save')} onPress={save} style={{ marginTop: 12 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const st = StyleSheet.create({
  input: { borderWidth: 1, borderRadius: 16, paddingHorizontal: 16, paddingVertical: 14, fontSize: 16 },
  seg: { flexDirection: 'row', borderRadius: 999, padding: 4 },
  segItem: { flex: 1, alignItems: 'center', paddingVertical: 9, borderRadius: 999 },
});
