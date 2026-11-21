/**
 * The study card: tap to flip; once the answer shows, swipe right (right)
 * or left (wrong), or use the buttons. Shared by the blitz and topic study.
 */
import { useEffect, useRef, useState } from 'react';
import { Animated, PanResponder, Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from 'react-native';

import { MathText } from './math-text';
import { Muted, Pill } from './ui';
import { useSettings } from '@/lib/settings';

const SWIPE = 110;

export function FlashCard({ cardKey, question, answer, onAnswer }: {
  cardKey: string; question: string; answer: string; onAnswer: (correct: boolean) => void;
}) {
  const { colors, t } = useSettings();
  const { width } = useWindowDimensions();
  const [flipped, setFlipped] = useState(false);
  const pan = useRef(new Animated.ValueXY()).current;
  const busy = useRef(false);

  // A new card: front side, back in the middle.
  useEffect(() => {
    setFlipped(false);
    pan.setValue({ x: 0, y: 0 });
    busy.current = false;
  }, [cardKey, pan]);

  const flyOut = (correct: boolean) => {
    if (busy.current) return;
    busy.current = true;
    Animated.timing(pan, { toValue: { x: (correct ? 1 : -1) * width * 1.3, y: 0 }, duration: 180, useNativeDriver: true })
      .start(() => onAnswer(correct));
  };

  const flippedRef = useRef(flipped);
  flippedRef.current = flipped;
  const flyRef = useRef(flyOut);
  flyRef.current = flyOut;

  const responder = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) => flippedRef.current && Math.abs(g.dx) > 8 && Math.abs(g.dx) > Math.abs(g.dy),
      onPanResponderMove: (_, g) => pan.setValue({ x: g.dx, y: g.dy * 0.2 }),
      onPanResponderRelease: (_, g) => {
        if (Math.abs(g.dx) > SWIPE) flyRef.current(g.dx > 0);
        else Animated.spring(pan, { toValue: { x: 0, y: 0 }, useNativeDriver: true }).start();
      },
      onPanResponderTerminate: () => Animated.spring(pan, { toValue: { x: 0, y: 0 }, useNativeDriver: true }).start(),
    }),
  ).current;

  const rotate = pan.x.interpolate({ inputRange: [-width, 0, width], outputRange: ['-12deg', '0deg', '12deg'] });
  const rightOpacity = pan.x.interpolate({ inputRange: [0, SWIPE], outputRange: [0, 1], extrapolate: 'clamp' });
  const wrongOpacity = pan.x.interpolate({ inputRange: [-SWIPE, 0], outputRange: [1, 0], extrapolate: 'clamp' });

  return (
    <>
      <View style={st.area}>
        <Animated.View
          {...responder.panHandlers}
          style={[st.card, { backgroundColor: colors.bg, borderColor: colors.line, transform: [{ translateX: pan.x }, { translateY: pan.y }, { rotate }] }]}
        >
          <Pressable style={st.inner} onPress={() => setFlipped((f) => !f)}>
            <Text style={[st.face, { color: colors.muted }]}>{(flipped ? t('blitz.answer') : t('blitz.question')).toUpperCase()}</Text>
            <ScrollView contentContainerStyle={st.textWrap}>
              <MathText key={flipped ? 'a' : 'q'} text={flipped ? answer : question} style={st.text} />
            </ScrollView>
            {!flipped ? <Muted style={{ fontSize: 13 }}>{t('blitz.tapToFlip')}</Muted> : null}
          </Pressable>
          <Animated.Text style={[st.stamp, st.stampRight, { color: colors.fg, borderColor: colors.fg, opacity: rightOpacity }]}>{t('blitz.right').toUpperCase()}</Animated.Text>
          <Animated.Text style={[st.stamp, st.stampWrong, { color: colors.fg, borderColor: colors.fg, opacity: wrongOpacity }]}>{t('blitz.wrong').toUpperCase()}</Animated.Text>
        </Animated.View>
      </View>
      <View style={[st.buttons, { opacity: flipped ? 1 : 0 }]} pointerEvents={flipped ? 'auto' : 'none'}>
        <Pill title={t('blitz.wrong')} ghost onPress={() => flyOut(false)} style={{ flex: 1 }} />
        <Pill title={t('blitz.right')} onPress={() => flyOut(true)} style={{ flex: 1 }} />
      </View>
    </>
  );
}

const st = StyleSheet.create({
  area: { flex: 1, paddingHorizontal: 24, paddingTop: 20, paddingBottom: 12 },
  card: { flex: 1, borderWidth: 1, borderRadius: 32, overflow: 'hidden', elevation: 2, shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 20, shadowOffset: { width: 0, height: 8 } },
  inner: { flex: 1, paddingHorizontal: 28, paddingTop: 22, paddingBottom: 22, alignItems: 'center' },
  face: { fontSize: 12, fontWeight: '600', letterSpacing: 1 },
  textWrap: { flexGrow: 1, justifyContent: 'center', paddingVertical: 16 },
  text: { fontSize: 24, fontWeight: '600', textAlign: 'center', lineHeight: 32 },
  stamp: { position: 'absolute', top: 22, borderWidth: 2, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 3, fontWeight: '700', fontSize: 14 },
  stampRight: { left: 22, transform: [{ rotate: '-8deg' }] },
  stampWrong: { right: 22, transform: [{ rotate: '8deg' }] },
  buttons: { flexDirection: 'row', gap: 12, paddingHorizontal: 24, paddingBottom: 56 },
});
