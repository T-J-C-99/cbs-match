"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, formatError } from "@/lib/apiClient";

type User = { 
  id: string; 
  email: string; 
  username?: string | null; 
  is_email_verified: boolean;
  tenant_slug?: string | null;
};

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  register: (payload: FormData | { email: string; password: string; username?: string; display_name?: string; cbs_year?: string; hometown?: string; gender_identity?: string; seeking_genders?: string[] }) => Promise<any>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
  /** Fetch wrapper with credentials: "include" for cookie-based auth */
  fetchWithAuth: (url: string, options?: RequestInit) => Promise<Response>;
  /** Verify email with 6-digit code */
  verifyEmail: (email: string, code: string) => Promise<void>;
  /** Resend verification code */
  resendVerificationCode: (email: string) => Promise<{ message?: string; dev_only?: { verification_code?: string } }>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

// Development-only debug logging
function debugLog(...args: unknown[]) {
  if (process.env.NODE_ENV !== "production") {
    console.log("[AuthProvider]", ...args);
  }
}

async function requestAuthJson<T = unknown>(url: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const isForm = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (!isForm && !headers.has("Content-Type") && init.body != null) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...init,
    headers,
    credentials: "include",
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(
      response.status,
      url,
      init.method || "GET",
      data,
      (data?.detail as string | undefined) || (data?.message as string | undefined) || "Request failed"
    );
  }

  return data as T;
}

/**
 * AuthProvider using httpOnly cookie-based session.
 * 
 * No localStorage tokens. Auth state comes from /auth/me endpoint.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  /**
   * Fetch current user from /auth/me endpoint.
   * Uses cookie session (credentials: "include" via apiClient).
   */
  const refreshMe = useCallback(async () => {
    debugLog("Fetching current user from /auth/me");
    
    try {
      const data = await requestAuthJson<{ user?: {
        id: string; 
        email: string; 
        username?: string; 
        is_email_verified: boolean;
        tenant_slug?: string;
      }; access_token?: string }>("/api/auth/me");
      
      if (!data?.user) {
        setUser(null);
        return;
      }
      debugLog("User fetched successfully:", data.user.email);
      setUser(data.user);
    } catch (error) {
      debugLog("Failed to fetch user:", formatError(error));
      setUser(null);
    }
  }, []);

  // Initial load - fetch user state on mount
  useEffect(() => {
    debugLog("Initial auth check starting...");
    refreshMe().finally(() => setLoading(false));
  }, [refreshMe]);

  /**
   * Login via cookie-based session.
   * Server sets httpOnly cookie, we just call /auth/me after.
   */
  const login = useCallback(async (identifier: string, password: string) => {
    debugLog(`Login attempt for: ${identifier}`);
    
    try {
      await requestAuthJson("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ identifier, password }),
      });
      
      // Fetch user state using the new session
      await refreshMe();
      
      debugLog("Login successful");
    } catch (error) {
      debugLog("Login failed:", formatError(error));
      throw error;
    }
  }, [refreshMe]);

  /**
   * Register via cookie-based session.
   * Server sets httpOnly cookie, we just call /auth/me after.
   */
  const register = useCallback(async (payload: FormData | { email: string; password: string; username?: string; display_name?: string; cbs_year?: string; hometown?: string; gender_identity?: string; seeking_genders?: string[] }) => {
    const isForm = typeof FormData !== "undefined" && payload instanceof FormData;
    debugLog(`Register attempt (isForm: ${isForm})`);
    
    try {
      await requestAuthJson("/api/auth/register", {
        method: "POST",
        body: isForm ? payload : JSON.stringify(payload),
      });
      
      // Fetch user state using the new session
      await refreshMe();
      
      debugLog("Register successful");
    } catch (error) {
      debugLog("Register failed:", formatError(error));
      throw error;
    }
  }, [refreshMe]);

  /**
   * Logout - clear cookie session on server.
   */
  const logout = useCallback(async () => {
    debugLog("Logout called");
    
    try {
      await requestAuthJson("/api/auth/logout", {
        method: "POST",
      });
    } catch (error) {
      debugLog("Logout request failed:", formatError(error));
    }
    
    setUser(null);
  }, []);

  /**
   * Fetch wrapper for backward compatibility.
   * Uses credentials: "include" for cookie-based auth.
   */
  const fetchWithAuth = useCallback(async (url: string, options?: RequestInit): Promise<Response> => {
    debugLog(`fetchWithAuth: ${options?.method || "GET"} ${url}`);
    
    const headers = new Headers(options?.headers);
    if (!headers.has("Content-Type") && !(options?.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: "include",
    });
    
    return response;
  }, []);

  /**
   * Verify email with 6-digit code.
   */
  const verifyEmail = useCallback(async (email: string, code: string): Promise<void> => {
    debugLog(`verifyEmail for: ${email}`);
    
    try {
      await requestAuthJson("/api/auth/verify-email", {
        method: "POST",
        body: JSON.stringify({ email, code }),
      });
      await refreshMe();
      debugLog("Email verified successfully");
    } catch (error) {
      debugLog("Email verification failed:", formatError(error));
      throw error;
    }
  }, [refreshMe]);

  /**
   * Resend verification code.
   */
  const resendVerificationCode = useCallback(async (email: string): Promise<{ message?: string; dev_only?: { verification_code?: string } }> => {
    debugLog(`resendVerificationCode for: ${email}`);
    
    try {
      const result = await requestAuthJson<{ message?: string; dev_only?: { verification_code?: string } }>("/api/auth/verify-email/resend", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      debugLog("Verification code resent");
      return result;
    } catch (error) {
      debugLog("Resend verification failed:", formatError(error));
      throw error;
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, login, register, logout, refreshMe, fetchWithAuth, verifyEmail, resendVerificationCode }),
    [user, loading, login, register, logout, refreshMe, fetchWithAuth, verifyEmail, resendVerificationCode]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}