/**
 * Login state (token in SecureStore) and background sync: runs after login,
 * whenever the network comes back, and shortly after local changes.
 */
import * as Network from 'expo-network';
import * as SecureStore from 'expo-secure-store';
import { useSQLiteContext } from 'expo-sqlite';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { ApiError, createApi, type Api } from './api';
import { getMeta, wipe } from './db';
import { syncOnce } from './sync';

type Auth = { server: string; token: string; nickname: string };

type Session = {
  ready: boolean;
  auth: Auth | null;
  api: Api | null;
  signIn: (server: string, login: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  setNickname: (nickname: string) => Promise<void>;
  syncing: boolean;
  syncError: boolean;
  lastSync: string | null;
  /** Bumps after every successful sync, so screens can reload. */
  revision: number;
  syncNow: () => Promise<void>;
  /** Ask for a sync soon (debounced) after a local change. */
  scheduleSync: () => void;
};

const Ctx = createContext<Session | null>(null);
const KEYS = { server: 'server', token: 'token', nickname: 'nickname' };

export function SessionProvider({ children }: { children: ReactNode }) {
  const db = useSQLiteContext();
  const [ready, setReady] = useState(false);
  const [auth, setAuth] = useState<Auth | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState(false);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const inFlight = useRef<Promise<void> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const api = useMemo(() => (auth ? createApi(auth.server, auth.token) : null), [auth]);

  useEffect(() => {
    (async () => {
      const [server, token, nickname] = await Promise.all(Object.values(KEYS).map((k) => SecureStore.getItemAsync(k)));
      if (server && token) setAuth({ server, token, nickname: nickname ?? '' });
      setLastSync(await getMeta(db, 'last_sync'));
      setReady(true);
    })();
  }, [db]);

  const signOut = useCallback(async () => {
    try {
      await api?.logout();
    } catch {
      /* offline: the token just stays valid on the server */
    }
    await Promise.all(Object.values(KEYS).map((k) => SecureStore.deleteItemAsync(k)));
    await wipe(db);
    setAuth(null);
    setLastSync(null);
  }, [api, db]);

  const syncNow = useCallback(async () => {
    if (!api) return;
    if (inFlight.current) return inFlight.current;
    const run = (async () => {
      setSyncing(true);
      try {
        await syncOnce(db, api);
        setSyncError(false);
        setLastSync(await getMeta(db, 'last_sync'));
        setRevision((r) => r + 1);
      } catch (e) {
        setSyncError(true);
        if (e instanceof ApiError && e.status === 401) await signOut();
      } finally {
        setSyncing(false);
        inFlight.current = null;
      }
    })();
    inFlight.current = run;
    return run;
  }, [api, db, signOut]);

  const scheduleSync = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void syncNow(), 3000);
  }, [syncNow]);

  // Sync on login / app start, and again whenever the network comes back.
  useEffect(() => {
    if (!api) return;
    void syncNow();
    const sub = Network.addNetworkStateListener((state) => {
      if (state.isConnected) void syncNow();
    });
    return () => sub.remove();
  }, [api, syncNow]);

  const signIn = useCallback(async (server: string, login: string, password: string) => {
    const res = await createApi(server, null).login(login, password);
    await SecureStore.setItemAsync(KEYS.server, server);
    await SecureStore.setItemAsync(KEYS.token, res.token);
    await SecureStore.setItemAsync(KEYS.nickname, res.user.nickname);
    await wipe(db); // a different account must not inherit local data
    setAuth({ server, token: res.token, nickname: res.user.nickname });
  }, [db]);

  const setNickname = useCallback(async (nickname: string) => {
    await SecureStore.setItemAsync(KEYS.nickname, nickname);
    setAuth((a) => (a ? { ...a, nickname } : a));
  }, []);

  const value = useMemo<Session>(
    () => ({ ready, auth, api, signIn, signOut, setNickname, syncing, syncError, lastSync, revision, syncNow, scheduleSync }),
    [ready, auth, api, signIn, signOut, setNickname, syncing, syncError, lastSync, revision, syncNow, scheduleSync],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): Session {
  const s = useContext(Ctx);
  if (!s) throw new Error('useSession outside SessionProvider');
  return s;
}
