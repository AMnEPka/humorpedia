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
  getNewsItem: (slug) => api.get(`/content/news/slug/${slug}`),
  
  // Articles
  getArticles: (params) => api.get('/content/articles', { params }),
  getArticle: (slug) => api.get(`/content/articles/slug/${slug}`),
  getPopularArticles: (limit = 5) => api.get('/content/articles', { params: { limit, sort: '-rating' } }),
  getRandomArticle: () => api.get('/content/articles/random'),
  
  // People
  getPeople: (params) => api.get('/content/people', { params }),
  getPerson: (slug) => api.get(`/content/people/slug/${slug}`),
  
  // Teams
  getTeams: (params) => api.get('/content/teams', { params }),
  getTeam: (slug) => api.get(`/content/teams/slug/${slug}`),
  getTeamsByCategory: (category, params) => api.get('/content/teams', { params: { ...params, category } }),
  
  // Shows
  getShows: (params) => api.get('/content/shows', { params }),
  getShow: (slug) => api.get(`/content/shows/slug/${slug}`),
  
  // Quizzes
  getQuizzes: (params) => api.get('/content/quizzes', { params }),
  getQuiz: (slug) => api.get(`/content/quizzes/slug/${slug}`),
  
  // Search
  search: (query, params) => api.get('/search', { params: { q: query, ...params } }),
  
  // Stats
  getStats: () => api.get('/stats'),
};

export default publicApi;
