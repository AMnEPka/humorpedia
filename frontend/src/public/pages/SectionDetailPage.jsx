import { useState, useEffect } from 'react';
import { useLocation, Link, useNavigate } from 'react-router-dom';
import { Loader2, ChevronRight, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import publicApi from '../utils/api';
import { ModuleList } from '../components/ModuleRenderer';

export default function SectionDetailPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [section, setSection] = useState(null);
  const [children, setChildren] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchSection = async () => {
      setLoading(true);
      setError('');
      try {
        // Get current path
        const path = location.pathname;
        
        // Fetch section by path
        const res = await publicApi.getSectionByPath(path);
        setSection(res.data);

        // Fetch children if show_children_list is true
        if (res.data.show_children_list) {
          const childrenRes = await publicApi.getSectionChildren(res.data._id);
          setChildren(childrenRes.data.items || []);
        }
      } catch (err) {
        setError('Раздел не найден');
      } finally {
        setLoading(false);
      }
    };
    fetchSection();
  }, [location.pathname]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error || !section) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
        <p className="text-gray-500 mb-4">{error || 'Раздел не найден'}</p>
        <Button asChild>
          <Link to="/">Вернуться на главную</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumbs */}
      {section.breadcrumbs && section.breadcrumbs.length > 0 && (
        <nav className="mb-6">
          <ol className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
            <li>
              <Link to="/" className="hover:text-blue-600">
                Главная
              </Link>
            </li>
            {section.breadcrumbs.map((crumb, idx) => (
              <li key={idx} className="flex items-center gap-2">
                <ChevronRight className="h-4 w-4" />
                <Link to={crumb.full_path} className="hover:text-blue-600">
                  {crumb.title}
                </Link>
              </li>
            ))}
            <li className="flex items-center gap-2">
              <ChevronRight className="h-4 w-4" />
              <span className="text-gray-900">{section.title}</span>
            </li>
          </ol>
        </nav>
      )}

      {/* Header */}
      <header className="mb-8">
        <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
          {section.title}
        </h1>

        {section.description && (
          <p className="text-lg text-gray-600 max-w-3xl">{section.description}</p>
        )}

        {section.tags && section.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {section.tags.map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </header>

      {/* Cover Image */}
      {section.cover_image && (
        <div className="mb-8">
          <img
            src={section.cover_image.url}
            alt={section.cover_image.alt || section.title}
            className="w-full h-auto rounded-lg shadow-lg object-cover max-h-[500px]"
          />
        </div>
      )}

      {/* Modular Content */}
      {section.modules && section.modules.length > 0 && (
        <div className="mb-8">
          <ModuleList modules={section.modules} />
        </div>
      )}

      {/* Children Sections */}
      {children.length > 0 && (
        <div className="mt-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">
            Подразделы
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {children.map((child) => (
              <Card
                key={child._id}
                className="hover:shadow-lg transition-shadow cursor-pointer"
                onClick={() => navigate(child.full_path)}
              >
                <CardHeader>
                  <CardTitle className="text-lg">{child.title}</CardTitle>
                </CardHeader>
                {child.description && (
                  <CardContent>
                    <p className="text-sm text-gray-600 line-clamp-3">
                      {child.description}
                    </p>
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Related Content */}
      {section.child_types && section.child_types.length > 0 && (
        <div className="mt-12 p-6 bg-blue-50 rounded-lg">
          <p className="text-sm text-gray-600">
            Этот раздел может содержать: {section.child_types.join(', ')}
          </p>
        </div>
      )}
    </div>
  );
}
