/** Study tab — design "D": the number of due cards in the middle, one main action. */
import { router, useFocusEffect } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Icon, Muted, Pill, Screen, type IconName } from '@/components/ui';
import { countDue, stats } from '@/lib/db';
import { MAX_STAGE } from '@/lib/scheduler';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function Study() {
  const db = useSQLiteContext();
  const { colors, t } = useSettings();
  const { revision } = useSession();
  const [due, setDue] = useState(0);
  const [total, setTotal] = useState(0);

  useFocusEffect(
    useCallback(() => {
      const load = async () => {
        setDue(await countDue(db, Date.now()));
        setTotal((await stats(db, MAX_STAGE)).total);
      };
      void load();
      const id = setInterval(load, 15000); // cards become due while you look at the screen
      return () => clearInterval(id);
    }, [db, revision]),
  );

  const action = (icon: IconName, label: string, onPress: () => void) => (
    <Pressable onPress={onPress} style={st.action}>
      <View style={[st.circle, { borderColor: colors.line }]}><Icon name={icon} size={20} /></View>
      <Text style={[st.actionText, { color: colors.fg }]}>{label}</Text>
    </Pressable>
  );

  return (
    <Screen>
      <Muted style={st.pool}>{t('study.inBlitz', { n: total })}</Muted>
      <View style={st.center}>
        <Text style={[st.big, { color: colors.fg }]}>{due}</Text>
        <Muted style={st.caption}>{due === 0 && total === 0 ? t('blitz.empty') : t('study.dueCaption')}</Muted>
        <Pill title={t('study.start')} onPress={() => router.push('/blitz')} style={st.start} />
        <View style={st.actions}>
          {action('layers', t('study.simple'), () => router.push('/simple'))}
          {action('plus', t('study.add'), () => router.push('/add-card'))}
          {action('list', t('study.all'), () => router.push('/cards'))}
        </View>
      </View>
    </Screen>
  );
}

const st = StyleSheet.create({
  pool: { paddingHorizontal: 24, paddingTop: 12, fontWeight: '600' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32, paddingBottom: 40 },
  big: { fontSize: 120, fontWeight: '600', letterSpacing: -6, lineHeight: 130 },
  caption: { fontSize: 16, marginTop: 6, textAlign: 'center' },
  start: { marginTop: 40, alignSelf: 'stretch' },
  actions: { flexDirection: 'row', marginTop: 44, alignSelf: 'stretch', justifyContent: 'space-between' },
  action: { flex: 1, alignItems: 'center', gap: 8 },
  circle: { width: 52, height: 52, borderRadius: 26, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  actionText: { fontSize: 13, fontWeight: '500' },
});
