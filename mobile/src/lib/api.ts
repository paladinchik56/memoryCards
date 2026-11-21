/** Thin client for the Django API (/api/, see api/views.py on the server). */

export class ApiError extends Error {
  constructor(public status: number, public code: string, public fields?: Record<string, string[]>) {
    super(`${status} ${code}`);
  }
}

export type LibraryTopic = { share_token: string; name: string; description: string; tags: string[]; owner: string; card_count: number };
export type SharedTopic = {
  uuid: string;
  share_token: string;
  name: string;
  description: string;
  tags: string[];
  owner: string;
  is_owner: boolean;
  is_added: boolean;
  cards: { uuid: string; question: string; answer: string; in_blitz: boolean }[];
};
export type User = { nickname: string; email: string };

export function createApi(server: string, token: string | null) {
  const base = server.replace(/\/+$/, '');

  async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (token) headers.Authorization = `Token ${token}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    let res: Response;
    try {
      res = await fetch(`${base}/api/${path}`, {
        method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal,
      });
    } catch {
      throw new ApiError(0, 'network');
    } finally {
      clearTimeout(timer);
    }
    if (res.status === 204) return undefined as T;
    let data: any = null;
    try {
      data = await res.json();
    } catch {
      /* non-JSON error page */
    }
    if (!res.ok) throw new ApiError(res.status, data?.error ?? 'http', data?.fields);
    return data as T;
  }

  return {
    login: (login: string, password: string) =>
      request<{ token: string; user: { nickname: string; email: string } }>('auth/token/', 'POST', { login, password }),
    logout: () => request<void>('auth/logout/', 'POST'),
    library: () => request<LibraryTopic[]>('library/'),
    shared: (shareToken: string) => request<SharedTopic>(`shared/${shareToken}/`),
    take: (shareToken: string, target: 'new' | null | string, cards?: string[]) =>
      request<{ added: number; skipped: number; collection: string | null }>(
        `shared/${shareToken}/take/`, 'POST', cards ? { target, cards } : { target },
      ),
    sync: (payload: object) => request<SyncResponse>('sync/', 'POST', payload),
    subscribe: (shareToken: string, add: boolean) =>
      request<{ is_added: boolean }>(`shared/${shareToken}/subscribe/`, add ? 'POST' : 'DELETE'),
    addToBlitz: (shareToken: string, cards: string[], reset: string[]) =>
      request<{ added: number; reset: number; skipped: number }>(`shared/${shareToken}/blitz/`, 'POST', { cards, reset }),
    copy: (shareToken: string, cards: string[], target: string) =>
      request<{ copied: number }>(`shared/${shareToken}/copy/`, 'POST', { cards, target }),
    author: (nickname: string) => request<{ nickname: string; topics: LibraryTopic[] }>(`authors/${encodeURIComponent(nickname)}/`),
    account: (body: { current_password: string; nickname?: string; new_password?: string }) =>
      request<User>('account/', 'POST', body),
  };
}

export type Api = ReturnType<typeof createApi>;

export type ServerCard = {
  uuid: string;
  question: string;
  answer: string;
  collection: string | null;
  source_collection: string | null;
  in_pool: boolean;
  stage: number;
  correct_count: number;
  is_reviewed: boolean;
  next_review_at: string;
  content_updated_at: string;
  created_at: string;
};

export type SyncResponse = {
  server_time: string;
  collections: { uuid: string; name: string; description: string; visibility: string; tags: string[]; updated_at: string }[];
  cards: ServerCard[];
  topic_runs: { collection: string; round: number; queue: string[]; wrong: string[]; round_total: number; correct_count: number; updated_at: string }[];
  added_topics: { uuid: string; share_token: string; name: string; description: string; tags: string[]; owner: string;
                  cards: { uuid: string; question: string; answer: string }[] }[];
  deleted: { kind: string; uuid: string }[];
  rejected: { kind: string; uuid: string | null; reason: string }[];
};
