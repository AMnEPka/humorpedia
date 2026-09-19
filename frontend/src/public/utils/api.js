import axios from 'axios';

// В dev при USE_API_PROXY запросы идут на тот же origin (/api), проксируются на бэкенд — без таймаутов и CORS.
const BACKEND_URL = (typeof window !== 'undefined' && window.__BACKEND_URL__)
  ? window.__BACKEND_URL__
  : (process.env.REACT_APP_BACKEND_URL || `${window.location.protocol}//${window.location.hostname}:8001`);
const USE_API_PROXY = process.env.REACT_APP_USE_API_PROXY === 'true';
const API_BASE_URL = USE_API_PROXY ? '/api' : BACKEND_URL + '/api';
if (typeof window !== 'undefined') console.log('[Public API] API_BASE_URL:', API_BASE_URL);

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

const pollAuthConfig = () => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('admin_token') : null;
  return token ? { headers: { Authorization: `Bearer ${token}` } } : {};
};

// Public API - no auth required
export const publicApi = {
  getPersonShows: (id) => api.get(`/show-appearances/people/${id}`),
  getTeamProjects: (idOrSlug) => api.get(`/show-appearances/teams/${encodeURIComponent(idOrSlug)}/projects`),
  // News
  getNews: (params) => api.get('/content/news', { params }),
  getNewsItem: (slug) => api.get(`/content/news/${slug}`),
  
  // Articles
  getArticles: (params) => api.get('/content/articles', { params }),
  getArticle: (slug) => api.get(`/content/articles/${slug}`),
  getPopularArticles: (limit = 5) => api.get('/content/articles', { params: { limit, sort: '-rating' } }),
  getRandomArticle: () => api.get('/content/articles/random'),
  getRandomContent: (type, params) => api.get(`/random/${type}`, { params }),
  getRecommendations: (contentType, contentId, limit) => api.get('/recommendations', {
    params: { content_type: contentType, content_id: contentId, ...(limit ? { limit } : {}) }
  }),
  getRelatedNews: (entityType, entityId) => api.get(
    `/related-news/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}`
  ),
  
  // People
  getPeople: (params) => api.get('/content/people', { params }),
  getPerson: (slug) => api.get(`/content/people/${slug}`),

  // Турниры, сезоны, составы (перекрёстные ссылки)
  getTeamParticipations: (idOrSlug, games = true) => api.get(`/competitions/teams/${idOrSlug}/participations`, { params: { games } }),
  getTeamMembers: (idOrSlug) => api.get(`/competitions/teams/${idOrSlug}/members`),
  getPersonCareer: (idOrSlug) => api.get(`/competitions/people/${idOrSlug}/career`),
  
  // Teams
  getTeams: (params) => api.get('/content/teams', { params }),
  getTeam: (slug) => api.get(`/content/teams/${slug}`),
  getTeamByPath: (path) => api.get(`/content/teams/by-path/${path}`),
  getTeamsByCategory: (category, params) => api.get('/content/teams', { params: { ...params, team_type: category } }),
  
  // Shows
  getShows: (params) => api.get('/content/shows', { params }),
  getShow: (slug) => api.get(`/content/shows/${slug}`),
  getShowByPath: (path) => api.get(`/content/shows/by-path/${path}`),
  getShowChildren: (parentSlug) => api.get(`/content/shows/${parentSlug}/children`),
  
  // Quizzes
  getQuizzes: (params) => api.get('/content/quizzes', { params }),
  getQuiz: (slug) => api.get(`/content/quizzes/${slug}`),
  
  // Sections
  getSections: (params) => api.get('/sections', { params }),
  getSectionsTree: (params) => api.get('/sections/tree', { params }),
  getSection: (idOrSlug) => api.get(`/sections/${idOrSlug}`),
  getSectionByPath: (path) => {
    // Удаляем ведущие и замыкающие слеши:
    // /kvn/vl-kvn и /kvn/vl-kvn/ обрабатываются одинаково
    const cleanPath = path
      .replace(/^\/+/, '')   // leading slashes
      .replace(/\/+$/, '');  // trailing slashes
    return api.get(`/sections/path/${cleanPath}`);
  },
  getSectionChildren: (sectionId, params) => api.get(`/sections/${sectionId}/children`, { params }),
  
  // KVN
  getKvn: (slugOrId) => api.get(`/content/kvn/${slugOrId}`),
  getKvnByPath: (path) => {
    const cleanPath = path
      .replace(/^\/+/, '')   // leading slashes
      .replace(/\/+$/, '');  // trailing slashes
    return api.get(`/content/kvn/by-path/${cleanPath}`);
  },
  getKvnChildren: (parentSlug) => api.get(`/content/kvn/${parentSlug}/children`),
  getKvnJuryStats: (params) => api.get('/content/kvn/jury-stats', { params }),
  
  // Cities (Geography)
  getCities: (params) => api.get('/cities/', { params }),
  getCity: (slug) => api.get(`/cities/${slug}`),
  getCityRelatedPeople: (cityId, limit = 100) => api.get(`/cities/${cityId}/related-people`, { params: { limit } }),
  getCityRelatedTeams: (cityId, limit = 500) => api.get(`/cities/${cityId}/related-teams`, { params: { limit } }),
  
  // Search
  search: (query, params) => api.get('/content/search', { params: { q: query, ...params } }),
  searchAutocomplete: (query) => api.get('/content/search/autocomplete', { params: { q: query, limit: 5 } }),
  searchByTag: (tag, params) => api.get(`/content/search/by-tag/${tag}`, { params }),
  
  // Stats
  getStats: () => api.get('/stats'),

  // Рейтинг узнаёт анонимного посетителя по cookie, в том числе при cross-origin разработке.
  getRating: (entityType, entityId) => api.get(
    `/ratings/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}`,
    { withCredentials: true }
  ),
  putRating: (entityType, entityId, score) => api.put(
    `/ratings/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}`,
    { score },
    { withCredentials: true }
  ),

  // Polls use the existing JWT contract. Public login/registration UI is a separate backlog item.
  getPoll: (id) => api.get(`/polls/${id}`, pollAuthConfig()),
  votePoll: (id, optionId) => api.post(`/polls/${id}/vote`, { option_id: optionId }, pollAuthConfig()),
};

export default publicApi;
