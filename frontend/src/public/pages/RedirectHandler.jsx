import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Компонент-перехватчик для старых URL humorpedia.ru.
 * Если текущий путь не совпал ни с одним маршрутом, пробуем найти редирект.
 */
export default function RedirectHandler() {
  const location = useLocation();
  const navigate = useNavigate();
  const [checking, setChecking] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const checkRedirect = async () => {
      setChecking(true);
      setNotFound(false);

      try {
        const path = location.pathname;
        const res = await fetch(
          `${BACKEND_URL}/api/redirects/lookup?path=${encodeURIComponent(path)}`
        );
        if (!res.ok) {
          throw new Error('Redirect lookup failed');
        }
        const data = await res.json();
        if (!cancelled && data.found && data.new_path) {
          // Редирект на новый путь (replace, чтобы не засорять историю)
          navigate(data.new_path, { replace: true });
          return;
        }
      } catch (err) {
        console.warn('Redirect lookup error:', err);
      }

      if (!cancelled) {
        setChecking(false);
        setNotFound(true);
      }
    };

    checkRedirect();
    return () => { cancelled = true; };
  }, [location.pathname, navigate]);

  if (checking) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto" />
          <p className="text-gray-500 text-sm">Ищем страницу…</p>
        </div>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center space-y-4 max-w-md mx-auto">
          <h1 className="text-6xl font-bold text-gray-300">404</h1>
          <p className="text-lg text-gray-600">Раздел не найден</p>
          <p className="text-sm text-gray-400">
            Запрашиваемая страница <code className="bg-gray-100 px-2 py-0.5 rounded text-xs">{location.pathname}</code> не существует.
          </p>
          <button
            onClick={() => navigate('/')}
            className="mt-4 inline-flex items-center px-6 py-2.5 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors text-sm"
          >
            Вернуться на главную
          </button>
        </div>
      </div>
    );
  }

  return null;
}
