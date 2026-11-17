import { Stack } from 'expo-router';

import { useSettings } from '@/lib/settings';

export default function LibraryLayout() {
  const { colors } = useSettings();
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg } }} />;
}
