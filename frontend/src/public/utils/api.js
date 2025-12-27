import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_BACKEND_URL + '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Public API - no auth required
export const publicApi = {
  // News
  getNews: (params) => api.get('/content/news', { params }),
  getNewsItem: (slug) => api.get(`/content/news/${slug}`),
  
  // Articles
  getArticles: (params) => api.get('/content/articles', { params }),
  getArticle: (slug) => api.get(`/content/articles/${slug}`),
  getPopularArticles: (limit = 5) => api.get('/content/articles', { params: { limit, sort: '-rating' } }),
  getRandomArticle: () => api.get('/content/articles/random'),
  
  // People
  getPeople: (params) => api.get('/content/people', { params }),
  getPerson: (slug) => api.get(`/content/people/${slug}`),
  
  // Teams
  getTeams: (params) => api.get('/content/teams', { params }),
  getTeam: (slug) => api.get(`/content/teams/${slug}`),
  getTeamsByCategory: (category, params) => api.get('/content/teams', { params: { ...params, category } }),
  
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
    // Remove leading slash if present
    const cleanPath = path.startsWith('/') ? path.substring(1) : path;
    return api.get(`/sections/path/${cleanPath}`);
  },
  getSectionChildren: (sectionId, params) => api.get(`/sections/${sectionId}/children`, { params }),
  
  // Search
  search: (query, params) => api.get('/content/search', { params: { q: query, ...params } }),
  searchAutocomplete: (query) => api.get('/content/search/autocomplete', { params: { q: query, limit: 5 } }),
  searchByTag: (tag, params) => api.get(`/content/search/by-tag/${tag}`, { params }),
  
  // Stats
  getStats: () => api.get('/stats'),
};

export default publicApi;
