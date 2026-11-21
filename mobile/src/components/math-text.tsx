/**
 * Card text that may contain LaTeX. Plain text renders as a normal <Text>;
 * text with formulas renders in a small WebView (MathML from KaTeX), which
 * passes touches through so the card can still be flipped and swiped.
 */
import { useMemo, useState } from 'react';
import { Text, View, type TextStyle } from 'react-native';
import { WebView } from 'react-native-webview';

import { hasMath, toHtml } from '@/lib/math';
import { useSettings } from '@/lib/settings';

export function MathText({ text, style, fontSize = 24, bold = true }: {
  text: string; style?: TextStyle; fontSize?: number; bold?: boolean;
}) {
  const { colors } = useSettings();
  const [height, setHeight] = useState(fontSize * 2);
  const math = hasMath(text);

  const html = useMemo(() => {
    if (!math) return '';
    return `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<style>
  html, body { margin: 0; padding: 0; background: transparent; }
  body { color: ${colors.fg}; font: ${bold ? 600 : 400} ${fontSize}px -apple-system, Roboto, "Noto Sans", sans-serif;
         text-align: center; white-space: pre-wrap; line-height: 1.35; overflow-wrap: anywhere; }
  math { font-size: 1.05em; }
  math[display="block"] { margin: .3em 0; }
</style></head><body><div id="c">${toHtml(text)}</div>
<script>
  function send() { window.ReactNativeWebView.postMessage(String(document.getElementById('c').getBoundingClientRect().height)); }
  send(); window.addEventListener('load', send); setTimeout(send, 150);
</script></body></html>`;
  }, [math, text, colors.fg, fontSize, bold]);

  if (!math) return <Text style={[{ color: colors.fg, fontSize, fontWeight: bold ? '600' : '400', textAlign: 'center' }, style]}>{text}</Text>;

  return (
    <View style={{ height, alignSelf: 'stretch' }} pointerEvents="none">
      <WebView
        originWhitelist={['*']}
        source={{ html }}
        style={{ backgroundColor: 'transparent' }}
        scrollEnabled={false}
        javaScriptEnabled
        onMessage={(e) => {
          const h = Math.ceil(Number(e.nativeEvent.data));
          if (h > 0 && Math.abs(h - height) > 1) setHeight(h + 4);
        }}
      />
    </View>
  );
}
