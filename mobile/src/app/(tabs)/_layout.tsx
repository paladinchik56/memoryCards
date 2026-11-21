import { Redirect, Tabs } from 'expo-router';
import { View } from 'react-native';

import { Icon } from '@/components/ui';
import { useSession } from '@/lib/session';
import { useSettings } from '@/lib/settings';

export default function TabsLayout() {
  const { colors, t } = useSettings();
  const { ready, auth, guest } = useSession();
  if (!ready) return <View style={{ flex: 1, backgroundColor: colors.bg }} />;
  if (!auth && !guest) return <Redirect href="/login" />;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: false,
        tabBarActiveTintColor: colors.fg,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: colors.bg, borderTopColor: colors.line },
      }}
    >
      <Tabs.Screen name="index" options={{ title: t('tab.study'), tabBarIcon: ({ color }) => <Icon name="book-open" color={color as string} size={24} /> }} />
      <Tabs.Screen name="library" options={{ title: t('tab.library'), tabBarIcon: ({ color }) => <Icon name="layers" color={color as string} size={24} /> }} />
      <Tabs.Screen name="profile" options={{ title: t('tab.profile'), tabBarIcon: ({ color }) => <Icon name="user" color={color as string} size={24} /> }} />
    </Tabs>
  );
}
