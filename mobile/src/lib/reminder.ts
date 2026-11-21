/** Daily local "time to review" notification, and the CSV export. */
import { File, Paths } from 'expo-file-system';
import * as Notifications from 'expo-notifications';
import * as Sharing from 'expo-sharing';
import Storage from 'expo-sqlite/kv-store';
import { Platform } from 'react-native';

export const REMINDER_TIMES = ['08:00', '12:00', '18:00', '20:00', '22:00'];

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: false, shouldSetBadge: false }),
});

export const getReminder = (): string | null => Storage.getItemSync('reminder');

/** Schedule the daily reminder at "HH:MM", or turn it off (null). Returns false if notifications are not allowed. */
export async function setReminder(time: string | null, text: { title: string; body: string }): Promise<boolean> {
  await Notifications.cancelAllScheduledNotificationsAsync();
  if (!time) {
    Storage.removeItemSync('reminder');
    return true;
  }
  if (Platform.OS === 'android') {
    // Android 13+ only shows the permission prompt once a channel exists.
    await Notifications.setNotificationChannelAsync('reminder', { name: text.title, importance: Notifications.AndroidImportance.DEFAULT });
  }
  const { status } = await Notifications.requestPermissionsAsync();
  if (status !== 'granted') return false;
  const [hour, minute] = time.split(':').map(Number);
  await Notifications.scheduleNotificationAsync({
    content: { title: text.title, body: text.body },
    trigger: { type: Notifications.SchedulableTriggerInputTypes.DAILY, hour, minute, channelId: 'reminder' },
  });
  Storage.setItemSync('reminder', time);
  return true;
}

export async function shareCsv(csv: string) {
  const file = new File(Paths.cache, 'cards.csv');
  file.create({ overwrite: true });
  file.write(csv);
  await Sharing.shareAsync(file.uri, { mimeType: 'text/csv', UTI: 'public.comma-separated-values-text' });
}
