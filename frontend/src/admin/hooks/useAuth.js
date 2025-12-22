import { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { authApi } from '../utils/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    const token = localStorage.getItem('admin_token');
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      const response = await authApi.me();
      setUser(response.data);
    } catch (error) {
      localStorage.removeItem('admin_token');
      localStorage.removeItem('admin_user');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

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
