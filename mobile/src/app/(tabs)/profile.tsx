import { router, useFocusEffect } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, View } from 'react-native';

import { ChoiceSheet } from '@/components/sheet';
import { Chip, Muted, Row, Screen, Section } from '@/components/ui';
import { exportCsv, stats } from '@/lib/db';
import { formatDuration, LANGUAGES, type Language } from '@/lib/i18n';
import { getReminder, REMINDER_TIMES, setReminder, shareCsv } from '@/lib/reminder';
import { MAX_STAGE } from '@/lib/scheduler';
import { useSession } from '@/lib/session';
import { useSettings, type Appearance } from '@/lib/settings';

type Picker = 'language' | 'appearance' | 'reminder' | null;

export default function Profile() {
  const db = useSQLiteContext();
  const { colors, t, lang, setLang, appearance, setAppearance } = useSettings();
  const { auth, syncing, syncError, lastSync, revision, syncNow, signOut } = useSession();
  const guest = !auth;
  const [numbers, setNumbers] = useState({ total: 0, learned: 0, streak: 0 });
  const [picker, setPicker] = useState<Picker>(null);
  const [reminder, setReminderState] = useState<string | null>(getReminder);

  useFocusEffect(useCallback(() => { void stats(db, MAX_STAGE).then(setNumbers); }, [db, revision]));

  const syncText = guest ? t('guest.hint') : syncing
    ? t('profile.syncing')
    : syncError
      ? t('profile.syncError')
      : t('profile.synced', {
          when: !lastSync ? t('profile.never')
            : Date.now() - Date.parse(lastSync) < 60000 ? t('time.justNow')
              : t('time.ago', { t: formatDuration(Date.now() - Date.parse(lastSync), t) }),
        });

  const pickReminder = async (time: string | null) => {
    const ok = await setReminder(time, { title: t('reminder.title'), body: t('reminder.body') });
    if (!ok) return Alert.alert(t('reminder.denied'));
    setReminderState(time);
  };

  const exportCards = async () => {
    try {
      await shareCsv(await exportCsv(db));
    } catch (e) {
      Alert.alert(String(e));
    }
  };

  const logout = () => Alert.alert(t('profile.logout'), t('profile.logoutConfirm2'), [
    { text: t('common.cancel'), style: 'cancel' },
    { text: t('profile.logout'), style: 'destructive', onPress: () => { void setReminder(null, { title: '', body: '' }); void signOut(); } },
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
            <Text style={[st.initial, { color: colors.muted }]}>{(auth?.nickname ?? '·').slice(0, 1).toUpperCase()}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[st.name, { color: colors.fg }]} numberOfLines={1}>{auth?.nickname ?? t('guest.name')}</Text>
            <Muted style={{ fontSize: 13, marginTop: 2 }}>{syncText}</Muted>
          </View>
          {guest
            ? <Chip title={t('guest.login')} active onPress={() => router.push('/login')} />
            : <Chip title={t('profile.refresh')} onPress={() => void syncNow()} />}
        </View>

        <View style={[st.stats, { borderColor: colors.line }]}>
          {stat(numbers.total, t('profile.inBlitz'))}
          {stat(numbers.learned, t('profile.learned'))}
          {stat(numbers.streak, t('profile.streak'))}
        </View>

        <Section title={t('profile.study')} />
        <Row title={t('profile.algorithm')} onPress={() => router.push('/algorithm')} />
        <Row title={t('profile.reminder')} value={reminder ?? t('reminder.off')} onPress={() => setPicker('reminder')} />

        <Section title={t('profile.app')} />
        <Row title={t('profile.language')} value={LANGUAGES[lang]} onPress={() => setPicker('language')} />
        <Row title={t('profile.appearance')} value={t(`appearance.${appearance}`)} onPress={() => setPicker('appearance')} />

        <Section title={t('profile.account')} />
        {guest ? null : <Row title={t('profile.nickPassword')} onPress={() => router.push('/account')} />}
        <Row title={t('profile.export')} value="CSV" onPress={() => void exportCards()} />
        {guest ? null : <Row title={t('profile.logout')} onPress={logout} chevron={false} />}
      </ScrollView>

      <ChoiceSheet<Language>
        visible={picker === 'language'} title={t('profile.language')} selected={lang} onClose={() => setPicker(null)}
        choices={(Object.keys(LANGUAGES) as Language[]).map((l) => ({ label: LANGUAGES[l], value: l }))} onPick={setLang}
      />
      <ChoiceSheet<Appearance>
        visible={picker === 'appearance'} title={t('profile.appearance')} selected={appearance} onClose={() => setPicker(null)}
        choices={(['system', 'light', 'dark'] as Appearance[]).map((a) => ({ label: t(`appearance.${a}`), value: a }))} onPick={setAppearance}
      />
      <ChoiceSheet<string | null>
        visible={picker === 'reminder'} title={t('profile.reminder')} selected={reminder} onClose={() => setPicker(null)}
        choices={[{ label: t('reminder.off'), value: null }, ...REMINDER_TIMES.map((time) => ({ label: time, value: time }))]}
        onPick={(v) => void pickReminder(v)}
      />
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
