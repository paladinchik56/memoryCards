import { Stack } from 'expo-router';
import { SQLiteProvider } from 'expo-sqlite';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { DB_NAME, migrate } from '@/lib/db';
import { SessionProvider } from '@/lib/session';
import { SettingsProvider, useSettings } from '@/lib/settings';

function Navigator() {
  const { colors, dark } = useSettings();
  return (
    <>
      <StatusBar style={dark ? 'light' : 'dark'} />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg } }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="login" />
        <Stack.Screen name="blitz" options={{ presentation: 'fullScreenModal', gestureEnabled: false }} />
        <Stack.Screen name="add-card" options={{ presentation: 'modal' }} />
        <Stack.Screen name="cards" />
        <Stack.Screen name="algorithm" />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <SQLiteProvider databaseName={DB_NAME} onInit={migrate}>
        <SettingsProvider>
          <SessionProvider>
            <Navigator />
          </SessionProvider>
        </SettingsProvider>
      </SQLiteProvider>
    </SafeAreaProvider>
  );
}
