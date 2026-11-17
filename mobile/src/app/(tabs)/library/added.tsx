import { router } from 'expo-router';
import { View } from 'react-native';

import { Muted, Screen, TopBar } from '@/components/ui';
import { useSettings } from '@/lib/settings';

export default function AddedTopics() {
  const { t } = useSettings();
  return (
    <Screen>
      <TopBar left="chevron-left" onLeft={() => router.back()} title={t('lib.added')} />
      <View style={{ padding: 24 }}>
        <Muted>{t('lib.addedSoon')}</Muted>
      </View>
    </Screen>
  );
}
