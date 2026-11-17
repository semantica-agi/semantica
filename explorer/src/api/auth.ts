/**
 * LDAP 登录会话管理与 API 凭证注入。
 *
 * 与后端的认证链对应：
 * - 登录通过 POST /api/auth/login 换取 HMAC 签名的 bearer token；
 * - token 保存在 localStorage，并在过期前主动失效；
 * - installAuthFetchBridge() 包装 window.fetch，为本站 /api/ 请求自动
 *   注入 Authorization 头，并在 401 时广播 semantica-auth-expired
 *   事件，让应用层回到登录界面。
 * 现有的 X-API-Key / 匿名模式不受影响：没有 token 时不注入任何头。
 */

const TOKEN_STORAGE_KEY = "semantica.auth.token";
const USER_STORAGE_KEY = "semantica.auth.user";
export const AUTH_EXPIRED_EVENT = "semantica-auth-expired";

export type AuthStatus = {
  anonymous: boolean;
  ldap: boolean;
  api_key: boolean;
};

export type AuthUser = {
  username: string;
  display_name: string | null;
  email: string | null;
  groups: string[];
};

type LoginSuccessPayload = {
  token_type: string;
  token: string;
  expires_at: string;
  user: AuthUser;
};

type MePayload = {
  mode: "ldap" | "api_key" | "anonymous";
  user: AuthUser | null;
};

type TokenPayload = {
  exp?: number;
};

function decodeTokenPayload(token: string): TokenPayload | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = atob(base64 + "=".repeat((4 - (base64.length % 4)) % 4));
    return JSON.parse(json) as TokenPayload;
  } catch {
    return null;
  }
}

function isTokenExpired(token: string): boolean {
  const payload = decodeTokenPayload(token);
  if (!payload || typeof payload.exp !== "number") return true;
  // 30 秒提前量，避免"刚拿到就过期"的边缘体验。
  return Date.now() / 1000 > payload.exp - 30;
}

/** 读取未过期的会话 token；过期或缺失时返回 null 并清理存储。 */
export function getStoredToken(): string | null {
  try {
    const token = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!token) return null;
    if (isTokenExpired(token)) {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
      return null;
    }
    return token;
  } catch {
    return null;
  }
}

export function peekStoredUser(): AuthUser | null {
  try {
    const raw = window.localStorage.getItem(USER_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthUser;
    return typeof parsed?.username === "string" ? parsed : null;
  } catch {
    return null;
  }
}

function storeSession(token: string, user: AuthUser): void {
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
}

/** 清除会话（退出登录 / token 失效）。 */
export function clearSession(): void {
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  window.localStorage.removeItem(USER_STORAGE_KEY);
}

export async function fetchAuthStatus(): Promise<AuthStatus | null> {
  try {
    const response = await window.fetch("/api/auth/status");
    if (!response.ok) return null;
    return (await response.json()) as AuthStatus;
  } catch {
    return null;
  }
}

/**
 * 用 LDAP 凭证换取会话。成功后写入存储并返回用户信息；
 * 失败时抛出带中文提示的 Error，由登录界面直接展示。
 */
export async function login(username: string, password: string): Promise<AuthUser> {
  let response: Response;
  try {
    response = await window.fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  } catch {
    throw new Error("无法连接认证服务，请稍后重试。");
  }
  if (response.ok) {
    const payload = (await response.json()) as LoginSuccessPayload;
    storeSession(payload.token, payload.user);
    return payload.user;
  }
  if (response.status === 401) throw new Error("用户名或密码错误。");
  if (response.status === 503) throw new Error("LDAP 登录未配置或认证服务暂不可用。");
  throw new Error("登录失败（" + response.status + "）。");
}

function buildBearerHeaders(token: string): Headers {
  return new Headers({ Authorization: "Bearer " + token });
}

/**
 * 校验本地 token 是否仍有效（GET /api/auth/me）。
 * 返回用户信息；token 缺失或已被服务端拒绝时返回 null 并清理会话。
 * 网络故障时保守地返回 null——调用方会退回登录界面。
 */
export async function verifyStoredSession(): Promise<AuthUser | null> {
  const token = getStoredToken();
  if (!token) return null;
  try {
    const response = await window.fetch("/api/auth/me", {
      headers: buildBearerHeaders(token),
    });
    if (!response.ok) {
      clearSession();
      return null;
    }
    const payload = (await response.json()) as MePayload;
    const user = payload.mode === "ldap" ? payload.user : null;
    if (!user) clearSession();
    return user;
  } catch {
    clearSession();
    return null;
  }
}

let bridgeInstalled = false;

function looksLikeApiRequest(input: RequestInfo | URL): { targetsApi: boolean; isAuthEndpoint: boolean } {
  try {
    const raw = typeof input === "string" || input instanceof URL ? input.toString() : input.url;
    const parsed = new URL(raw, window.location.origin);
    const sameOrigin = parsed.origin === window.location.origin;
    const targetsApi = sameOrigin && parsed.pathname.startsWith("/api/");
    const isAuthEndpoint = parsed.pathname.startsWith("/api/auth/");
    return { targetsApi, isAuthEndpoint };
  } catch {
    return { targetsApi: false, isAuthEndpoint: false };
  }
}

function mergeBearerHeader(input: RequestInfo | URL, init: RequestInit | undefined, token: string): RequestInit {
  const existing = init?.headers ?? (typeof input === "object" && !(input instanceof URL) ? input.headers : undefined);
  const headers = new Headers(existing);
  if (!headers.has("Authorization")) headers.set("Authorization", "Bearer " + token);
  return { ...(init ?? {}), headers };
}

/**
 * 包装 window.fetch：为本站 /api/ 请求附加 Authorization: Bearer 头，
 * 并在 401 时广播 AUTH_EXPIRED_EVENT。幂等；登录/状态端点不注入、
 * 不触发过期事件。
 */
export function installAuthFetchBridge(): void {
  if (bridgeInstalled) return;
  bridgeInstalled = true;
  const originalFetch = window.fetch.bind(window);

  window.fetch = async (
    input: RequestInfo | URL,
    init?: RequestInit,
  ): Promise<Response> => {
    const { targetsApi, isAuthEndpoint } = looksLikeApiRequest(input);

    let effectiveInit = init;
    if (targetsApi && !isAuthEndpoint) {
      const token = getStoredToken();
      if (token) {
        effectiveInit = mergeBearerHeader(input, init, token);
      }
    }

    const response = await originalFetch(input, effectiveInit);

    if (response.status === 401 && targetsApi && !isAuthEndpoint) {
      window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
    }
    return response;
  };
}