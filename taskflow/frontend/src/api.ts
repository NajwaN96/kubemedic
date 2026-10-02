export type TaskStatus = "pending" | "completed";

export type Task = {
  id: number;
  title: string;
  description: string;
  status: TaskStatus;
  created_at: string;
};

export type ApiStatus = "loading" | "healthy" | "not_ready" | "unavailable";

const base = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(0, "The API is unreachable.");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text) as unknown;
    } catch {
      throw new ApiError(response.status, "The API returned an unexpected error.");
    }
  }
  if (!response.ok) {
    throw new ApiError(response.status, messageFromPayload(payload));
  }
  return payload as T;
}

function messageFromPayload(payload: unknown): string {
  if (!payload || typeof payload !== "object" || !("detail" in payload)) {
    return "The API returned an unexpected error.";
  }
  const detail = (payload as { detail: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const first = detail.find((item) => item && typeof item === "object" && "msg" in item) as
      | { msg?: string }
      | undefined;
    if (first?.msg) {
      return first.msg;
    }
  }
  return "The request was rejected.";
}

export function getTasks(): Promise<Task[]> {
  return request<Task[]>("/tasks");
}

export function createTask(input: { title: string; description: string }): Promise<Task> {
  return request<Task>("/tasks", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateTask(
  id: number,
  changes: { title?: string; description?: string; status?: TaskStatus },
): Promise<Task> {
  return request<Task>(`/tasks/${id}`, {
    method: "PUT",
    body: JSON.stringify(changes),
  });
}

export function deleteTask(id: number): Promise<void> {
  return request<void>(`/tasks/${id}`, { method: "DELETE" });
}

export async function getApiStatus(): Promise<Exclude<ApiStatus, "loading">> {
  try {
    const health = await fetch(`${base}/health`, { cache: "no-store" });
    if (!health.ok) {
      return "unavailable";
    }
    const ready = await fetch(`${base}/ready`, { cache: "no-store" });
    return ready.ok ? "healthy" : "not_ready";
  } catch {
    return "unavailable";
  }
}
