/** Thin client for the Django API (/api/, see api/views.py on the server). */

export class ApiError extends Error {
  constructor(public status: number, public code: string) {
    super(`${status} ${code}`);
  }
}

export type LibraryTopic = { share_token: string; name: string; description: string; owner: string; card_count: number };
export type SharedTopic = {
  share_token: string;
  name: string;
  description: string;
  owner: string;
  is_owner: boolean;
  cards: { uuid: string; question: string; answer: string }[];
};

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
    if (!res.ok) throw new ApiError(res.status, data?.error ?? 'http');
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
  };
}

export type Api = ReturnType<typeof createApi>;

export type ServerCard = {
  uuid: string;
  question: string;
  answer: string;
  collection: string | null;
  stage: number;
  correct_count: number;
  is_reviewed: boolean;
  next_review_at: string;
  content_updated_at: string;
  created_at: string;
};

export type SyncResponse = {
  server_time: string;
  collections: { uuid: string; name: string; description: string; visibility: string; updated_at: string }[];
  cards: ServerCard[];
  deleted: { kind: string; uuid: string }[];
  rejected: { kind: string; uuid: string | null; reason: string }[];
};
