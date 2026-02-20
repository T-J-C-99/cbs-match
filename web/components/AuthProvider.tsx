"use client";

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { apiClient, apiGet, apiPost, ApiError, formatError } from "@/lib/apiClient";

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
  const refreshMe = async () => {
    debugLog("Fetching current user from /auth/me");
    
    try {
      const data = await apiGet<{ 
        id: string; 
        email: string; 
        username?: string; 
        is_email_verified: boolean;
        tenant_slug?: string;
      }>("/auth/me");
      
      debugLog("User fetched successfully:", data.email);
      setUser(data);
    } catch (error) {
      debugLog("Failed to fetch user:", formatError(error));
      setUser(null);
    }
  };

  // Initial load - fetch user state on mount
  useEffect(() => {
    debugLog("Initial auth check starting...");
    refreshMe().finally(() => setLoading(false));
  }, []);

  /**
   * Login via cookie-based session.
   * Server sets httpOnly cookie, we just call /auth/me after.
   */
  const login = async (identifier: string, password: string) => {
    debugLog(`Login attempt for: ${identifier}`);
    
    try {
      // Login sets httpOnly cookie session
      await apiPost("/auth/login", { identifier, password });
      
      // Fetch user state using the new session
      await refreshMe();
      
      debugLog("Login successful");
    } catch (error) {
      debugLog("Login failed:", formatError(error));
      throw error;
    }
  };

  /**
   * Register via cookie-based session.
   * Server sets httpOnly cookie, we just call /auth/me after.
   */
  const register = async (payload: FormData | { email: string; password: string; username?: string; display_name?: string; cbs_year?: string; hometown?: string; gender_identity?: string; seeking_genders?: string[] }) => {
    const isForm = typeof FormData !== "undefined" && payload instanceof FormData;
    debugLog(`Register attempt (isForm: ${isForm})`);
    
    try {
      if (isForm) {
        // For FormData, use raw fetch with credentials
        const response = await fetch("/api/auth/register", {
          method: "POST",
          body: payload,
          credentials: "include",
        });
        
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new ApiError(
            response.status,
            "/api/auth/register",
            "POST",
            data,
            data?.detail || data?.message || "Registration failed"
          );
        }
      } else {
        await apiPost("/auth/register", payload);
      }
      
      // Fetch user state using the new session
      await refreshMe();
      
      debugLog("Register successful");
    } catch (error) {
      debugLog("Register failed:", formatError(error));
      throw error;
    }
  };

  /**
   * Logout - clear cookie session on server.
   */
  const logout = async () => {
    debugLog("Logout called");
    
    try {
      await apiPost("/auth/logout");
    } catch (error) {
      debugLog("Logout request failed:", formatError(error));
    }
    
    setUser(null);
  };

  /**
   * Fetch wrapper for backward compatibility.
   * Uses credentials: "include" for cookie-based auth.
   */
  const fetchWithAuth = async (url: string, options?: RequestInit): Promise<Response> => {
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
  };

  /**
   * Verify email with 6-digit code.
   */
  const verifyEmail = async (email: string, code: string): Promise<void> => {
    debugLog(`verifyEmail for: ${email}`);
    
    try {
      await apiPost("/auth/verify-email", { email, code });
      await refreshMe();
      debugLog("Email verified successfully");
    } catch (error) {
      debugLog("Email verification failed:", formatError(error));
      throw error;
    }
  };

  /**
   * Resend verification code.
   */
  const resendVerificationCode = async (email: string): Promise<{ message?: string; dev_only?: { verification_code?: string } }> => {
    debugLog(`resendVerificationCode for: ${email}`);
    
    try {
      const result = await apiPost<{ message?: string; dev_only?: { verification_code?: string } }>("/auth/resend-verification", { email });
      debugLog("Verification code resent");
      return result;
    } catch (error) {
      debugLog("Resend verification failed:", formatError(error));
      throw error;
    }
  };

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, login, register, logout, refreshMe, fetchWithAuth, verifyEmail, resendVerificationCode }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}