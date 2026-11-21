import Constants from 'expo-constants';
import { Redirect, router } from 'expo-router';
import { useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { Muted, Pill, Screen, Title } from '@/components/ui';
import { ApiError } from '@/lib/api';
import { OtherAccountData, useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

/** In development the Django server usually runs on the same computer as Metro. */
function guessServer(): string {
  const host = Constants.expoConfig?.hostUri?.split(':')[0];
  if (host) return `http://${host}:8000`;
  return (Constants.expoConfig?.extra?.defaultServer as string | undefined) ?? 'http://192.168.0.1:8000';
}

export default function Login() {
  const { colors, t } = useSettings();
  const { auth, signIn, continueAsGuest } = useSession();
  const [server, setServer] = useState(guessServer);
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (auth) return <Redirect href="/" />;

  const submit = async (replace = false) => {
    setBusy(true);
    setError(null);
    try {
      await signIn(server.trim(), login.trim(), password, replace);
      router.replace('/');
    } catch (e) {
      if (e instanceof OtherAccountData) {
        Alert.alert(t('login.title'), t('login.otherAccount', { owner: e.owner }), [
          { text: t('common.cancel'), style: 'cancel' },
          { text: t('login.replace'), style: 'destructive', onPress: () => void submit(true) },
        ]);
      } else {
        setError(e instanceof ApiError && e.status === 400 ? t('login.failed') : t('login.network'));
      }
    } finally {
      setBusy(false);
    }
  };

  const guest = () => {
    continueAsGuest();
    router.replace('/');
  };

  const input = [st.input, { color: colors.fg, borderColor: colors.line }];
  return (
    <Screen edges={['top', 'bottom']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={st.wrap}>
        <Title>{t('login.title')}</Title>
        <View style={{ gap: 12, marginTop: 28 }}>
          <Muted style={st.label}>{t('login.server')}</Muted>
          <TextInput style={input} value={server} onChangeText={setServer} autoCapitalize="none" autoCorrect={false} keyboardType="url" />
          <Muted style={st.label}>{t('login.login')}</Muted>
          <TextInput style={input} value={login} onChangeText={setLogin} autoCapitalize="none" autoCorrect={false} />
          <Muted style={st.label}>{t('login.password')}</Muted>
          <TextInput style={input} value={password} onChangeText={setPassword} secureTextEntry onSubmitEditing={() => void submit()} />
        </View>
        {error ? <Text style={[st.error, { color: colors.fg }]}>{error}</Text> : null}
        <Pill title={t('login.submit')} onPress={() => void submit()} loading={busy} disabled={!login || !password} style={{ marginTop: 28 }} />
        <Pressable onPress={guest} style={{ alignItems: 'center', paddingTop: 22 }} hitSlop={8}>
          <Text style={{ color: colors.fg, fontSize: 15, fontWeight: '500' }}>{t('login.guest')}</Text>
          <Muted style={{ fontSize: 13, textAlign: 'center', marginTop: 4 }}>{t('login.guestHint')}</Muted>
        </Pressable>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const st = StyleSheet.create({
  wrap: { flex: 1, justifyContent: 'center', paddingHorizontal: 24 },
  label: { fontSize: 13, marginBottom: -6 },
  input: { borderWidth: 1, borderRadius: 16, paddingHorizontal: 16, paddingVertical: 14, fontSize: 16 },
  error: { marginTop: 18, fontSize: 14, fontWeight: '500' },
});
