const STORAGE_KEY = 'humorpedia_teams';
const STORAGE_VERSION = '1.0';
const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 часа в миллисекундах

/**
 * Локальное хранилище данных команд (persistent storage, не кэш)
 * Хранит данные команд локально и обновляет их раз в 24 часа
 */
class TeamStorage {
  constructor() {
    this.data = this.loadFromStorage();
  }

  loadFromStorage() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) {
        return { 
          teams: {}, 
          version: STORAGE_VERSION, 
          lastUpdate: null 
        };
      }
      
      const parsed = JSON.parse(stored);
      
      // Проверяем версию формата
      if (parsed.version !== STORAGE_VERSION) {
        // Версия изменилась - очищаем старое хранилище
        return { 
          teams: {}, 
          version: STORAGE_VERSION, 
          lastUpdate: null 
        };
      }
      
      return parsed;
    } catch (e) {
      console.warn('Failed to load teams from storage:', e);
      return { 
        teams: {}, 
        version: STORAGE_VERSION, 
        lastUpdate: null 
      };
    }
  }

  saveToStorage() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.data));
    } catch (e) {
      console.warn('Failed to save teams to storage:', e);
      // Если localStorage переполнен, пытаемся очистить старые данные
      try {
        const teams = this.data.teams;
        const sorted = Object.entries(teams)
          .sort((a, b) => {
            const timeA = new Date(a[1].stored_at || 0).getTime();
            const timeB = new Date(b[1].stored_at || 0).getTime();
            return timeB - timeA; // Новые первыми
          });
        
        // Оставляем только последние 1000 команд
        this.data.teams = Object.fromEntries(sorted.slice(0, 1000));
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.data));
      } catch (e2) {
        console.error('Failed to save teams even after cleanup:', e2);
      }
    }
  }

  /**
   * Проверяет, нужно ли обновлять данные
   */
  needsUpdate() {
    if (!this.data.lastUpdate) {
      return true;
    }
    
    const now = Date.now();
    const lastUpdate = new Date(this.data.lastUpdate).getTime();
    return (now - lastUpdate) > CACHE_DURATION;
  }

  /**
   * Обновляет данные команд из ответа API сезона
   */
  updateFromSeason(teamData, version) {
    if (!teamData || typeof teamData !== 'object') {
      return;
    }
    
    const now = new Date().toISOString();
    
    // Обновляем существующие данные
    Object.keys(teamData).forEach(slug => {
      const team = teamData[slug];
      this.data.teams[slug] = {
        name: team.name || '',
        city: team.city || '',
        updated_at: team.updated_at || now,
        stored_at: now
      };
    });
    
    this.data.lastUpdate = now;
    this.data.lastVersion = version;
    this.saveToStorage();
  }

  /**
   * Получает данные команды по slug
   */
  getTeam(slug) {
    return this.data.teams[slug] || null;
  }

  /**
   * Получает данные нескольких команд
   */
  getTeams(slugs) {
    const result = {};
    slugs.forEach(slug => {
      if (this.data.teams[slug]) {
        result[slug] = this.data.teams[slug];
      }
    });
    return result;
  }

  /**
   * Принудительное обновление (по запросу пользователя)
   */
  clear() {
    this.data = { 
      teams: {}, 
      version: STORAGE_VERSION, 
      lastUpdate: null 
    };
    this.saveToStorage();
  }

  /**
   * Получить статистику хранилища
   */
  getStats() {
    return {
      teamsCount: Object.keys(this.data.teams).length,
      lastUpdate: this.data.lastUpdate,
      needsUpdate: this.needsUpdate()
    };
  }
}

// Singleton instance
export const teamStorage = new TeamStorage();
