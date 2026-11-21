/** Change nickname and/or password (needs the server). */
import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput } from 'react-native';

import { Muted, Pill, Screen, TopBar } from '@/components/ui';
import { ApiError } from '@/lib/api';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function Account() {
  const { colors, t } = useSettings();
  const { api, auth, setNickname } = useSession();
  const [nickname, setNick] = useState(auth?.nickname ?? '');
  const [newPassword, setNewPassword] = useState('');
  const [current, setCurrent] = useState('');
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const save = async () => {
    if (!api) return;
    setBusy(true);
    setNote(null);
    try {
      const body: { current_password: string; nickname?: string; new_password?: string } = { current_password: current };
      if (nickname.trim() && nickname.trim() !== auth?.nickname) body.nickname = nickname.trim();
      if (newPassword) body.new_password = newPassword;
      const user = await api.account(body);
      await setNickname(user.nickname);
      setNewPassword('');
      setCurrent('');
      setNote(t('account.saved'));
    } catch (e) {
      if (e instanceof ApiError && e.code === 'wrong_password') setNote(t('account.wrong'));
      else if (e instanceof ApiError && e.fields) {
        setNote(e.fields.nickname?.includes('taken') ? t('account.taken') : Object.values(e.fields).flat().join('\n'));
      } else setNote(t('lib.needNetwork'));
    } finally {
      setBusy(false);
    }
  };

  const input = [st.input, { color: colors.fg, borderColor: colors.line }];
  return (
    <Screen edges={['top', 'bottom']}>
      <TopBar left="chevron-left" onLeft={() => router.back()} title={t('account.title')} />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ paddingHorizontal: 24, gap: 10 }} keyboardShouldPersistTaps="handled">
          <Muted style={st.label}>{t('account.nickname')}</Muted>
          <TextInput style={input} value={nickname} onChangeText={setNick} autoCapitalize="none" autoCorrect={false} />
          <Muted style={st.label}>{t('account.newPassword')}</Muted>
          <TextInput style={input} value={newPassword} onChangeText={setNewPassword} secureTextEntry />
          <Muted style={st.label}>{t('account.current')}</Muted>
          <TextInput style={input} value={current} onChangeText={setCurrent} secureTextEntry />
          {note ? <Text style={{ color: colors.fg, fontWeight: '500', marginTop: 6 }}>{note}</Text> : null}
          <Pill title={t('account.save')} onPress={save} loading={busy} disabled={!current} style={{ marginTop: 14 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const st = StyleSheet.create({
  label: { fontSize: 13, marginTop: 8 },
  input: { borderWidth: 1, borderRadius: 16, paddingHorizontal: 16, paddingVertical: 14, fontSize: 16 },
});
