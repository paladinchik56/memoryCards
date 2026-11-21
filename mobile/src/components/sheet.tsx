/**
 * Bottom sheets: a generic one, a list of choices (Android's Alert only fits
 * three buttons), and the "already in the blitz: skip or reset" dialog.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Icon, Muted, Pill } from './ui';
import { useSettings } from '@/lib/settings';

export function Sheet({ visible, onClose, children }: { visible: boolean; onClose: () => void; children: ReactNode }) {
  const { colors } = useSettings();
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <Pressable style={{ flex: 1, backgroundColor: colors.dim }} onPress={onClose} />
      <View style={[st.sheet, { backgroundColor: colors.bg, paddingBottom: Math.max(insets.bottom, 16) + 20 }]}>{children}</View>
    </Modal>
  );
}

export type Choice<T> = { label: string; value: T; hint?: string };

export function ChoiceSheet<T>({ visible, title, choices, selected, onPick, onClose }: {
  visible: boolean; title: string; choices: Choice<T>[]; selected?: T; onPick: (v: T) => void; onClose: () => void;
}) {
  const { colors } = useSettings();
  return (
    <Sheet visible={visible} onClose={onClose}>
      <Text style={[st.title, { color: colors.fg }]}>{title}</Text>
      <ScrollView style={{ maxHeight: 420, marginTop: 8 }}>
        {choices.map((c, i) => (
          <Pressable key={i} onPress={() => { onPick(c.value); onClose(); }} style={[st.row, { borderBottomColor: colors.line }]}>
            <View style={{ flex: 1 }}>
              <Text style={{ color: colors.fg, fontSize: 16 }}>{c.label}</Text>
              {c.hint ? <Muted style={{ fontSize: 13, marginTop: 2 }}>{c.hint}</Muted> : null}
            </View>
            {c.value === selected ? <Icon name="check" size={18} /> : null}
          </Pressable>
        ))}
      </ScrollView>
    </Sheet>
  );
}

export function Checkbox({ on }: { on: boolean }) {
  const { colors } = useSettings();
  return (
    <View style={[st.box, on ? { backgroundColor: colors.fg, borderColor: colors.fg } : { borderColor: colors.muted }]}>
      {on ? <Icon name="check" size={14} color={colors.bg} /> : null}
    </View>
  );
}

/**
 * Some picked cards are already in the blitz: per card "skip" or "reset
 * progress", with "apply to all". Calls onConfirm with the uuids to reset.
 */
export function ConflictSheet({ visible, newCount, conflicts, onConfirm, onClose }: {
  visible: boolean; newCount: number; conflicts: { uuid: string; question: string }[];
  onConfirm: (reset: string[]) => void; onClose: () => void;
}) {
  const { colors, t } = useSettings();
  const [reset, setReset] = useState<Set<string>>(new Set());
  const [all, setAll] = useState(true);
  useEffect(() => { if (visible) { setReset(new Set()); setAll(true); } }, [visible]);

  const choose = (uuid: string, doReset: boolean) => {
    if (all) return setReset(doReset ? new Set(conflicts.map((c) => c.uuid)) : new Set());
    const n = new Set(reset);
    if (doReset) n.add(uuid); else n.delete(uuid);
    setReset(n);
  };

  const seg = (label: string, on: boolean, onPress: () => void) => (
    <Pressable onPress={onPress} style={[st.segItem, on && { backgroundColor: colors.bg }]}>
      <Text style={{ fontSize: 12, fontWeight: '500', color: on ? colors.fg : colors.muted }}>{label}</Text>
    </Pressable>
  );

  return (
    <Sheet visible={visible} onClose={onClose}>
      <Text style={[st.title, { color: colors.fg }]}>{t('conflict.title', { n: conflicts.length })}</Text>
      <Muted style={{ fontSize: 14, marginTop: 4 }}>{t('conflict.hint', { n: newCount })}</Muted>
      <ScrollView style={{ maxHeight: 300, marginTop: 8 }}>
        {conflicts.map((c) => (
          <View key={c.uuid} style={[st.row, { borderBottomColor: colors.line }]}>
            <Text style={{ flex: 1, color: colors.fg, fontSize: 15 }} numberOfLines={2}>{c.question}</Text>
            <View style={[st.seg, { backgroundColor: colors.soft }]}>
              {seg(t('conflict.skip'), !reset.has(c.uuid), () => choose(c.uuid, false))}
              {seg(t('conflict.reset'), reset.has(c.uuid), () => choose(c.uuid, true))}
            </View>
          </View>
        ))}
      </ScrollView>
      <Pressable onPress={() => setAll(!all)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 14 }}>
        <Checkbox on={all} />
        <Text style={{ color: colors.fg, fontSize: 15 }}>{t('conflict.applyAll')}</Text>
      </Pressable>
      <Pill title={t('conflict.confirm')} onPress={() => onConfirm([...reset])} />
    </Sheet>
  );
}

const st = StyleSheet.create({
  sheet: { borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingHorizontal: 24, paddingTop: 22 },
  title: { fontSize: 20, fontWeight: '700' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth },
  box: { width: 22, height: 22, borderRadius: 7, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  seg: { flexDirection: 'row', borderRadius: 999, padding: 3 },
  segItem: { paddingVertical: 6, paddingHorizontal: 10, borderRadius: 999 },
});
