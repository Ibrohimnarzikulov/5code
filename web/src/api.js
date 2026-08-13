/**
 * Backend bilan ishlovchi yagona qatlam.
 * Vite proxy tufayli yo'llar nisbiy (`/api/...`) — port farqi bilinmaydi.
 */

const TOKEN_KEY = "ca_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

/** 401 da avtomatik chiqarish uchun ilova qo'yadigan callback. */
let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn;
};

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Autentifikatsiyalangan JSON so'rov.
 *
 * @param {string} path — `/api/...`
 * @param {RequestInit & {auth?: boolean}} options
 * @returns {Promise<any>} JSON javob (204 uchun `null`)
 *
 * @example
 *   const me = await api("/api/auth/me");
 */
export async function api(path, options = {}) {
  const { auth = true, headers, ...rest } = options;
  const finalHeaders = { "Content-Type": "application/json", ...headers };

  const token = getToken();
  if (auth && token) finalHeaders.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(path, { ...rest, headers: finalHeaders });
  } catch {
    throw new ApiError("Serverga ulanib bo'lmadi (backend ishlayaptimi?)", 0);
  }

  if (response.status === 401 && auth) {
    clearToken();
    onUnauthorized();
    throw new ApiError("Sessiya tugadi — qayta kiring", 401);
  }
  if (response.status === 204) return null;

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(body.detail || `Xatolik (${response.status})`, response.status);
  }
  return body;
}

/**
 * Chat SSE oqimini o'qiydi va har hodisani `onEvent` ga uzatadi.
 *
 * @param {{conversationId: number|null, message: string,
 *          onEvent: (e: object) => void, signal?: AbortSignal}} params
 *
 * @example
 *   await streamChat({ conversationId: null, message: "Salom",
 *                      onEvent: (e) => console.log(e.type) });
 */
export async function streamChat({ conversationId, message, onEvent, signal }) {
  const response = await fetch("/api/chat", {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify({ conversation_id: conversationId, message }),
  });

  if (response.status === 401) {
    clearToken();
    onUnauthorized();
    throw new ApiError("Sessiya tugadi", 401);
  }
  if (!response.ok || !response.body) {
    throw new ApiError(`Server javobi: ${response.status}`, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let tail = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    tail += decoder.decode(value, { stream: true });
    const lines = tail.split("\n");
    tail = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        onEvent(JSON.parse(line.slice(6)));
      } catch {
        /* yarim kelgan qator — keyingi bo'lakda to'liq bo'ladi */
      }
    }
  }
}
