import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

// Create axios instance
const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('admin_token');
      localStorage.removeItem('admin_user');
      window.location.href = '/admin/login';
    }
    return Promise.reject(error);
  }
);

export default api;

// Auth API
export const authApi = {
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
};

// Content API
export const contentApi = {
  // People
  listPeople: (params) => api.get('/content/people', { params }),
  getPerson: (id) => api.get(`/content/people/${id}`),
  createPerson: (data) => api.post('/content/people', data),
  updatePerson: (id, data) => api.put(`/content/people/${id}`, data),
  deletePerson: (id) => api.delete(`/content/people/${id}`),

  // Teams
  listTeams: (params) => api.get('/content/teams', { params }),
  getTeam: (id) => api.get(`/content/teams/${id}`),
  createTeam: (data) => api.post('/content/teams', data),
  updateTeam: (id, data) => api.put(`/content/teams/${id}`, data),
  deleteTeam: (id) => api.delete(`/content/teams/${id}`),

  // Shows
  listShows: (params) => api.get('/content/shows', { params }),
  getShow: (id) => api.get(`/content/shows/${id}`),
  createShow: (data) => api.post('/content/shows', data),
  updateShow: (id, data) => api.put(`/content/shows/${id}`, data),
  deleteShow: (id) => api.delete(`/content/shows/${id}`),

  // Articles
  listArticles: (params) => api.get('/content/articles', { params }),
  getArticle: (id) => api.get(`/content/articles/${id}`),
  createArticle: (data) => api.post('/content/articles', data),
  updateArticle: (id, data) => api.put(`/content/articles/${id}`, data),
  deleteArticle: (id) => api.delete(`/content/articles/${id}`),

  // News
  listNews: (params) => api.get('/content/news', { params }),
  getNews: (id) => api.get(`/content/news/${id}`),
  createNews: (data) => api.post('/content/news', data),
  updateNews: (id, data) => api.put(`/content/news/${id}`, data),
  deleteNews: (id) => api.delete(`/content/news/${id}`),

  // Quizzes
  listQuizzes: (params) => api.get('/content/quizzes', { params }),
  getQuiz: (id) => api.get(`/content/quizzes/${id}`),
  createQuiz: (data) => api.post('/content/quizzes', data),
  updateQuiz: (id, data) => api.put(`/content/quizzes/${id}`, data),
  deleteQuiz: (id) => api.delete(`/content/quizzes/${id}`),

  // Wiki
  listWiki: (params) => api.get('/content/wiki', { params }),
  getWiki: (id) => api.get(`/content/wiki/${id}`),
  createWiki: (data) => api.post('/content/wiki', data),
  updateWiki: (id, data) => api.put(`/content/wiki/${id}`, data),
  deleteWiki: (id) => api.delete(`/content/wiki/${id}`),

  // Search
  search: (params) => api.get('/content/search', { params }),
};

// Stats API
export const statsApi = {
  getStats: () => api.get('/stats'),
  getRandom: (type) => api.get(`/random/${type}`),
};

// Users API
export const usersApi = {
  list: (params) => api.get('/users', { params }),
  get: (id) => api.get(`/users/${id}`),
  update: (id, data) => api.put(`/users/${id}`, data),
  ban: (id) => api.post(`/users/${id}/ban`),
  unban: (id) => api.post(`/users/${id}/unban`),
  delete: (id) => api.delete(`/users/${id}`),
};

// Tags API
export const tagsApi = {
  list: (params) => api.get('/tags', { params }),
  getPopular: (limit) => api.get('/tags/popular', { params: { limit } }),
  create: (data) => api.post('/tags', data),
  update: (id, data) => api.put(`/tags/${id}`, data),
  delete: (id) => api.delete(`/tags/${id}`),
};

// Comments API
export const commentsApi = {
  list: (params) => api.get('/comments', { params }),
  listPending: (params) => api.get('/comments/pending', { params }),
  approve: (id) => api.post(`/comments/${id}/approve`),
  reject: (id) => api.post(`/comments/${id}/reject`),
  delete: (id) => api.delete(`/comments/${id}`),
};

// Media API
export const mediaApi = {
  list: (params) => api.get('/media', { params }),
  upload: (file, metadata) => {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata?.alt) formData.append('alt', metadata.alt);
    if (metadata?.caption) formData.append('caption', metadata.caption);
    return api.post('/media/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  update: (id, data) => api.put(`/media/${id}`, data),
  delete: (id) => api.delete(`/media/${id}`),
};

// Templates API
export const templatesApi = {
  list: (params) => api.get('/templates', { params }),
  get: (id) => api.get(`/templates/${id}`),
  getDefault: (contentType) => api.get(`/templates/default/${contentType}`),
  create: (data) => api.post('/templates', data),
  update: (id, data) => api.put(`/templates/${id}`, data),
  setDefault: (id) => api.post(`/templates/${id}/set-default`),
  delete: (id) => api.delete(`/templates/${id}`),
  getModuleTypes: () => api.get('/templates/modules/types'),
};
