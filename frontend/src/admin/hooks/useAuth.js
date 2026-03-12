import React, { useState, useEffect, useCallback, useRef, createContext, useContext } from 'react';
import { authApi } from '../utils/api';

const AuthContext = createContext(null);

// How often to silently refresh the token (ms)
const REFRESH_INTERVAL_MS = 6 * 60 * 60 * 1000; // 6 hours

export function AuthProvider({ children }) {
  // Optimistic: restore user from localStorage immediately so UI doesn't flash
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('admin_user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);
  const refreshTimerRef = useRef(null);

  /**
   * Verify the current token against the server.
   * CRITICAL: does NOT clear localStorage on network errors — only on confirmed 401.
   */
  const checkAuth = useCallback(async () => {
    const token = localStorage.getItem('admin_token');
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }

    try {
      const response = await authApi.me();
      const freshUser = response.data;
      setUser(freshUser);
      // Keep localStorage in sync
      localStorage.setItem('admin_user', JSON.stringify(freshUser));
    } catch (error) {
      const status = error.response?.status;

      if (status === 401 || status === 403) {
        // Server explicitly says token is invalid / user is banned
        localStorage.removeItem('admin_token');
        localStorage.removeItem('admin_user');
        setUser(null);
      }
      // For network errors (no response) or 5xx — keep the current user
      // The token is likely still valid, the server is just temporarily unreachable
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Silently refresh the token in background.
   * Keeps the session alive without user interaction.
   */
  const silentRefresh = useCallback(async () => {
    const token = localStorage.getItem('admin_token');
    if (!token) return;

    try {
      const response = await authApi.refresh();
      const { access_token, user: freshUser } = response.data;
      localStorage.setItem('admin_token', access_token);
      if (freshUser) {
        localStorage.setItem('admin_user', JSON.stringify(freshUser));
        setUser(freshUser);
      }
    } catch {
      // Silent failure — interceptor handles 401 with its own refresh logic
    }
  }, []);

  // On mount: verify token & start refresh timer
  useEffect(() => {
    checkAuth();

    // Periodically refresh the token to prevent expiration during long sessions
    refreshTimerRef.current = setInterval(silentRefresh, REFRESH_INTERVAL_MS);

    return () => {
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    };
  }, [checkAuth, silentRefresh]);

  const login = async (email, password) => {
    const response = await authApi.login({ email, password });
    const { access_token, user: userData } = response.data;
    
    // Check if user has admin/editor role
    if (!['admin', 'editor', 'moderator'].includes(userData.role)) {
      throw new Error('Недостаточно прав для доступа к админ-панели');
    }

    localStorage.setItem('admin_token', access_token);
    localStorage.setItem('admin_user', JSON.stringify(userData));
    setUser(userData);
    return userData;
  };

  const logout = () => {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_user');
    setUser(null);
    if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
  };

  const isAdmin = user?.role === 'admin';
  const isEditor = ['admin', 'editor'].includes(user?.role);
  const isModerator = ['admin', 'editor', 'moderator'].includes(user?.role);

  return (
    <AuthContext.Provider value={{ 
      user, 
      loading, 
      login, 
      logout, 
      isAdmin, 
      isEditor, 
      isModerator,
      checkAuth 
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
