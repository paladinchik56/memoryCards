/** Minimal building blocks of the monochrome "D" design. */
import Feather from '@expo/vector-icons/Feather';
import type { ComponentProps, ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import { SafeAreaView, type Edge } from 'react-native-safe-area-context';

import { useSettings } from '@/lib/settings';

export type IconName = ComponentProps<typeof Feather>['name'];

export function Icon({ name, size = 22, color }: { name: IconName; size?: number; color?: ComponentProps<typeof Feather>['color'] }) {
  const { colors } = useSettings();
  return <Feather name={name} size={size} color={color ?? colors.fg} />;
}

export function Screen({ children, edges = ['top'], style }: { children: ReactNode; edges?: Edge[]; style?: StyleProp<ViewStyle> }) {
  const { colors } = useSettings();
  return <SafeAreaView edges={edges} style={[{ flex: 1, backgroundColor: colors.bg }, style]}>{children}</SafeAreaView>;
}

export function TopBar({ title, left, onLeft, right }: { title?: string; left?: IconName; onLeft?: () => void; right?: ReactNode }) {
  const { colors } = useSettings();
  return (
    <View style={s.top}>
      <Pressable onPress={onLeft} hitSlop={12} style={s.topSide}>
        {left ? <Icon name={left} size={24} /> : null}
      </Pressable>
      <Text style={[s.topTitle, { color: colors.fg }]} numberOfLines={1}>{title}</Text>
      <View style={[s.topSide, { alignItems: 'flex-end' }]}>{right}</View>
    </View>
  );
}

export function Pill({ title, onPress, ghost, disabled, loading, style }: {
  title: string; onPress?: () => void; ghost?: boolean; disabled?: boolean; loading?: boolean; style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useSettings();
  const fg = ghost ? colors.fg : colors.bg;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        s.pill,
        ghost ? { borderWidth: 1, borderColor: colors.line } : { backgroundColor: colors.fg },
        { opacity: disabled ? 0.4 : pressed ? 0.75 : 1 },
        style,
      ]}
    >
      {loading ? <ActivityIndicator color={fg} /> : <Text style={[s.pillText, { color: fg }]}>{title}</Text>}
    </Pressable>
  );
}

export function Chip({ title, icon, active, onPress }: { title: string; icon?: IconName; active?: boolean; onPress?: () => void }) {
  const { colors } = useSettings();
  const fg = active ? colors.bg : colors.fg;
  return (
    <Pressable
      onPress={onPress}
      hitSlop={6}
      style={[s.chip, active ? { backgroundColor: colors.fg, borderColor: colors.fg } : { borderColor: colors.line }]}
    >
      {icon ? <Icon name={icon} size={14} color={fg} /> : null}
      <Text style={[s.chipText, { color: fg }]} numberOfLines={1}>{title}</Text>
    </Pressable>
  );
}

export function Section({ title }: { title: string }) {
  const { colors } = useSettings();
  return <Text style={[s.section, { color: colors.muted }]}>{title.toUpperCase()}</Text>;
}

export function Row({ title, subtitle, value, onPress, chevron = !!onPress, left, disabled }: {
  title: string; subtitle?: string; value?: string; onPress?: () => void; chevron?: boolean; left?: ReactNode; disabled?: boolean;
}) {
  const { colors } = useSettings();
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress || disabled}
      style={({ pressed }) => [s.row, { borderBottomColor: colors.line, opacity: disabled ? 0.45 : pressed ? 0.6 : 1 }]}
    >
      {left}
      <View style={{ flex: 1 }}>
        <Text style={[s.rowTitle, { color: colors.fg }]}>{title}</Text>
        {subtitle ? <Text style={[s.rowSub, { color: colors.muted }]} numberOfLines={2}>{subtitle}</Text> : null}
      </View>
      {value ? <Text style={[s.rowValue, { color: colors.muted }]}>{value}</Text> : null}
      {chevron ? <Icon name="chevron-right" size={18} color={colors.muted} /> : null}
    </Pressable>
  );
}

export function Muted({ children, style }: { children: ReactNode; style?: object }) {
  const { colors } = useSettings();
  return <Text style={[{ color: colors.muted, fontSize: 15 }, style]}>{children}</Text>;
}

export function Title({ children, style }: { children: ReactNode; style?: object }) {
  const { colors } = useSettings();
  return <Text style={[{ color: colors.fg, fontSize: 30, fontWeight: '700', letterSpacing: -0.5 }, style]}>{children}</Text>;
}

export const s = StyleSheet.create({
  top: { height: 52, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16 },
  topSide: { minWidth: 40, height: 40, justifyContent: 'center' },
  topTitle: { flex: 1, textAlign: 'center', fontSize: 16, fontWeight: '600' },
  pill: { borderRadius: 999, paddingVertical: 17, paddingHorizontal: 20, alignItems: 'center', justifyContent: 'center' },
  pillText: { fontSize: 16, fontWeight: '600' },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderRadius: 999, paddingVertical: 7, paddingHorizontal: 13, alignSelf: 'flex-start' },
  chipText: { fontSize: 13, fontWeight: '500', maxWidth: 220 },
  section: { fontSize: 12, fontWeight: '600', letterSpacing: 1, paddingTop: 22, paddingBottom: 4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 15, borderBottomWidth: StyleSheet.hairlineWidth },
  rowTitle: { fontSize: 16, fontWeight: '500' },
  rowSub: { fontSize: 13, marginTop: 3 },
  rowValue: { fontSize: 14 },
});
