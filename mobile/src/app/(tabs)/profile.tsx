import { router, useFocusEffect } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Chip, Muted, Row, Screen, Section } from '@/components/ui';
import { stats } from '@/lib/db';
import { formatDuration, LANGUAGES, type Language } from '@/lib/i18n';
import { MAX_STAGE } from '@/lib/scheduler';
import { useSession } from '@/lib/session';
import { useSettings, type Appearance } from '@/lib/settings';

export default function Profile() {
  const db = useSQLiteContext();
  const { colors, t, lang, setLang, appearance, setAppearance } = useSettings();
  const { auth, syncing, syncError, lastSync, revision, syncNow, signOut } = useSession();
  const [numbers, setNumbers] = useState({ total: 0, learned: 0, streak: 0 });

  useFocusEffect(useCallback(() => { void stats(db, MAX_STAGE).then(setNumbers); }, [db, revision]));

  const syncText = syncing
    ? t('profile.syncing')
    : syncError
      ? t('profile.syncError')
      : t('profile.synced', {
          when: !lastSync ? t('profile.never')
            : Date.now() - Date.parse(lastSync) < 60000 ? t('time.justNow')
              : t('time.ago', { t: formatDuration(Date.now() - Date.parse(lastSync), t) }),
        });

  const chooseLanguage = () => Alert.alert(t('profile.language'), undefined, [
    ...(Object.keys(LANGUAGES) as Language[]).map((l) => ({ text: LANGUAGES[l], onPress: () => setLang(l) })),
    { text: t('common.cancel'), style: 'cancel' as const },
  ]);
  const chooseAppearance = () => Alert.alert(t('profile.appearance'), undefined, [
    ...(['system', 'light', 'dark'] as Appearance[]).map((a) => ({ text: t(`appearance.${a}`), onPress: () => setAppearance(a) })),
    { text: t('common.cancel'), style: 'cancel' as const },
  ]);
  const logout = () => Alert.alert(t('profile.logout'), t('profile.logoutConfirm'), [
    { text: t('common.cancel'), style: 'cancel' },
    { text: t('profile.logout'), style: 'destructive', onPress: () => void signOut() },
  ]);

  const stat = (n: number, label: string) => (
    <View style={{ flex: 1, alignItems: 'center' }}>
      <Text style={[st.statN, { color: colors.fg }]}>{n}</Text>
      <Muted style={{ fontSize: 12, marginTop: 1 }}>{label}</Muted>
    </View>
  );

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 40 }}>
        <View style={st.head}>
          <View style={[st.avatar, { backgroundColor: colors.soft }]}>
            <Text style={[st.initial, { color: colors.muted }]}>{(auth?.nickname ?? '?').slice(0, 1).toUpperCase()}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[st.name, { color: colors.fg }]} numberOfLines={1}>{auth?.nickname}</Text>
            <Muted style={{ fontSize: 13, marginTop: 2 }}>{syncText}</Muted>
          </View>
          <Chip title={t('profile.refresh')} onPress={() => void syncNow()} />
        </View>

        <View style={[st.stats, { borderColor: colors.line }]}>
          {stat(numbers.total, t('profile.inBlitz'))}
          {stat(numbers.learned, t('profile.learned'))}
          {stat(numbers.streak, t('profile.streak'))}
        </View>

        <Section title={t('profile.study')} />
        <Row title={t('profile.algorithm')} onPress={() => router.push('/algorithm')} />
        <Row title={t('profile.reminder')} value={t('profile.soon')} disabled />

        <Section title={t('profile.app')} />
        <Row title={t('profile.language')} value={LANGUAGES[lang]} onPress={chooseLanguage} />
        <Row title={t('profile.appearance')} value={t(`appearance.${appearance}`)} onPress={chooseAppearance} />

        <Section title={t('profile.account')} />
        <Row title={t('profile.nickPassword')} value={t('profile.soon')} disabled />
        <Row title={t('profile.export')} value={t('profile.soon')} disabled />
        <Row title={t('profile.logout')} onPress={logout} chevron={false} />
      </ScrollView>
    </Screen>
  );
}

const st = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingTop: 18 },
  avatar: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center' },
  initial: { fontSize: 22, fontWeight: '700' },
  name: { fontSize: 22, fontWeight: '700' },
  stats: { flexDirection: 'row', marginTop: 18, borderWidth: 1, borderRadius: 20, paddingVertical: 13 },
  statN: { fontSize: 24, fontWeight: '700' },
});
