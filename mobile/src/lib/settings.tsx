/** Language and appearance preferences + the color palette derived from them. */
import { getLocales } from 'expo-localization';
import Storage from 'expo-sqlite/kv-store';
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import { useColorScheme } from 'react-native';

import { LANGUAGES, translator, type Language, type T } from './i18n';

export type Appearance = 'system' | 'light' | 'dark';

const LIGHT = { bg: '#ffffff', fg: '#111111', muted: '#9a9a9a', line: '#ececec', soft: '#f5f5f4', dim: 'rgba(0,0,0,0.3)' };
const DARK: typeof LIGHT = { bg: '#0e0e0f', fg: '#f2f2f2', muted: '#76767b', line: '#232326', soft: '#1a1a1c', dim: 'rgba(0,0,0,0.55)' };
export type Colors = typeof LIGHT;

type Settings = {
  lang: Language;
  setLang: (l: Language) => void;
  appearance: Appearance;
  setAppearance: (a: Appearance) => void;
  dark: boolean;
  colors: Colors;
  t: T;
};

const Ctx = createContext<Settings | null>(null);

function deviceLanguage(): Language {
  const code = getLocales()[0]?.languageCode ?? 'en';
  return code in LANGUAGES ? (code as Language) : 'en';
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Language>(() => (Storage.getItemSync('lang') as Language | null) ?? deviceLanguage());
  const [appearance, setAppearanceState] = useState<Appearance>(
    () => (Storage.getItemSync('appearance') as Appearance | null) ?? 'system',
  );
  const system = useColorScheme();
  const dark = appearance === 'dark' || (appearance === 'system' && system === 'dark');

  const value = useMemo<Settings>(
    () => ({
      lang,
      setLang: (l) => {
        Storage.setItemSync('lang', l);
        setLangState(l);
      },
      appearance,
      setAppearance: (a) => {
        Storage.setItemSync('appearance', a);
        setAppearanceState(a);
      },
      dark,
      colors: dark ? DARK : LIGHT,
      t: translator(lang),
    }),
    [lang, appearance, dark],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSettings(): Settings {
  const s = useContext(Ctx);
  if (!s) throw new Error('useSettings outside SettingsProvider');
  return s;
}
