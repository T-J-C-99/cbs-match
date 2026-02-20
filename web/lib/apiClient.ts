/**
 * Centralized API client for web app.
 * 
 * Design principles:
 * 1. Uses ONLY httpOnly cookie session for auth (no localStorage tokens)
 * 2. Always sends credentials: "include" for cookie-based auth
 * 3. Provides typed error handling with trace_id for debugging
 * 4. Tenant is resolved server-side from user record (no X-Tenant-Slug for user routes)
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * Typed API error with structured information
 */
export class ApiError extends Error {
  status: number;
  endpoint: string;
  method: string;
  body: Record<string, unknown>;
  traceId: string | null;
  reason: string | null;

  constructor(
    status: number,
    endpoint: string,
    method: string,
    body: Record<string, unknown>,
    message?: string
  ) {
    super(message || String(body?.message || body?.detail || "API request failed"));
    this.name = "ApiError";
    this.status = status;
    this.endpoint = endpoint;
    this.method = method;
    this.body = body;
    this.traceId = (body?.trace_id as string) || null;
    this.reason = (body?.reason as string) || null;
  }
}

/**
 * Format an error for display in UI.
 * NEVER renders raw objects - always returns a readable string.
 */
export function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    // Include trace_id for support/debugging
    const trace = error.traceId ? ` (trace: ${error.traceId.slice(0, 8)})` : "";
    const reason = error.reason ? `: ${error.reason.replace(/_/g, " ")}` : "";
    return `${error.message}${reason}${trace}`;
  }
  
  if (error instanceof Error) {
    return error.message || "An unexpected error occurred";
  }
  
  if (typeof error === "string") {
    return error;
  }
  
  return "An unexpected error occurred";
}

/**
 * Options for API requests
 */
export interface ApiRequestOptions extends Omit<RequestInit, "credentials"> {
  /** Skip throwing on non-2xx (return raw response) */
  raw?: boolean;
}

/**
 * Make an API request with cookie-based auth.
 * 
 * - Always includes credentials: "include" for httpOnly cookie session
 * - Automatically parses JSON responses
 * - Throws ApiError on non-2xx with structured error info
 */
export async function apiClient<T = unknown>(
  endpoint: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const { raw, ...fetchOptions } = options;
  
  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint}`;
  const method = fetchOptions.method || "GET";
  
  // Build headers
  const headers = new Headers(fetchOptions.headers);
  const isFormData = typeof FormData !== "undefined" && fetchOptions.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  
  // Make request with credentials for cookie auth
  const response = await fetch(url, {
    ...fetchOptions,
    headers,
    credentials: "include", // Always include cookies for session auth
  });
  
  // Parse response body
  let body: Record<string, unknown> = {};
  try {
    const text = await response.text();
    if (text) {
      body = JSON.parse(text);
    }
  } catch {
    // Empty or non-JSON response
  }
  
  // Return raw response if requested
  if (raw) {
    return { status: response.status, body } as T;
  }
  
  // Throw structured error on non-2xx
  if (!response.ok) {
    throw new ApiError(
      response.status,
      endpoint,
      method,
      body,
      body?.detail as string | undefined || body?.message as string | undefined
    );
  }
  
  return body as T;
}

/**
 * GET request with cookie auth
 */
export async function apiGet<T = unknown>(endpoint: string): Promise<T> {
  return apiClient<T>(endpoint, { method: "GET" });
}

/**
 * POST request with cookie auth
 */
export async function apiPost<T = unknown>(endpoint: string, body?: unknown): Promise<T> {
  return apiClient<T>(endpoint, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}

/**
 * PUT request with cookie auth
 */
export async function apiPut<T = unknown>(endpoint: string, body?: unknown): Promise<T> {
  return apiClient<T>(endpoint, {
    method: "PUT",
    body: body ? JSON.stringify(body) : undefined,
  });
}

/**
 * DELETE request with cookie auth
 */
export async function apiDelete<T = unknown>(endpoint: string): Promise<T> {
  return apiClient<T>(endpoint, { method: "DELETE" });
}

/**
 * PATCH request with cookie auth
 */
export async function apiPatch<T = unknown>(endpoint: string, body?: unknown): Promise<T> {
  return apiClient<T>(endpoint, {
    method: "PATCH",
    body: body ? JSON.stringify(body) : undefined,
  });
}

// Export constants
export { API_BASE };