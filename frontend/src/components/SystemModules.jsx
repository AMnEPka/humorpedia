/**
 * Компоненты для рендеринга системных модулей на публичных страницах.
 * Эти модули берут данные из основных полей документа (poster, facts, tags, rating, social_links).
 */

import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import EmojiRating from '@/components/EmojiRating';
import { ExternalLink } from 'lucide-react';

/**
 * Модуль фото/постера
 */
export function PosterPhotoModule({ data, moduleData, className = '' }) {
  const imageUrl = data.poster || data.cover_image?.url || data.image || data.photo;
  const altText = data.cover_image?.alt || data.title || data.full_name || data.name;
  const size = moduleData?.size || 'medium';
  const shape = moduleData?.shape || 'rounded';
  
  const sizeClasses = {
    small: 'w-32 h-32',
    medium: 'w-full aspect-[3/4]',
    large: 'w-full aspect-[2/3]'
  };
  
  const shapeClasses = {
    square: 'rounded-none',
    rounded: 'rounded-xl',
    circle: 'rounded-full'
  };

  if (!imageUrl) {
    return (
      <div className={`${sizeClasses[size]} ${shapeClasses[shape]} bg-muted flex items-center justify-center ${className}`}>
        <span className="text-4xl font-bold text-muted-foreground">
          {(data.title || data.full_name || data.name || '?').charAt(0).toUpperCase()}
        </span>
      </div>
    );
  }

  return (
    <div className={`${sizeClasses[size]} ${shapeClasses[shape]} overflow-hidden bg-muted shadow-lg ${className}`}>
      <img 
        src={imageUrl} 
        alt={altText}
        className="w-full h-full object-cover object-top"
      />
    </div>
  );
}

/**
 * Функция для парсинга даты из текстового формата (например, "9 декабря 1988 года" или "25 мая")
 */
function parseDateFromText(dateText) {
  if (!dateText) return null;
  
  // Убираем возраст в скобках, если он есть
  const textWithoutAge = dateText.replace(/\s*\(\d+\s+лет\)\s*$/, '').trim();
  
  // Пытаемся найти год (4 цифры)
  const yearMatch = textWithoutAge.match(/\b(\d{4})\b/);
  if (!yearMatch) {
    // Если года нет, возвращаем null (не можем рассчитать возраст)
    return null;
  }
  
  const year = parseInt(yearMatch[1]);
  
  // Парсим месяц
  const months = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
  ];
  
  let month = -1;
  let day = 1;
  
  for (let i = 0; i < months.length; i++) {
    if (textWithoutAge.includes(months[i])) {
      month = i;
      // Пытаемся найти день перед месяцем
      const dayMatch = textWithoutAge.match(new RegExp(`(\\d+)\\s+${months[i]}`));
      if (dayMatch) {
        day = parseInt(dayMatch[1]);
      }
      break;
    }
  }
  
  if (month === -1) return null;
  
  try {
    const date = new Date(year, month, day);
    if (isNaN(date.getTime())) return null;
    return date;
  } catch (e) {
    return null;
  }
}

/**
 * Функция для проверки наличия года в текстовой дате
 */
function hasYearInDate(dateText) {
  if (!dateText) return false;
  // Убираем возраст в скобках перед проверкой
  const textWithoutAge = dateText.replace(/\s*\(\d+\s+лет\)\s*$/, '').trim();
  return /\b\d{4}\b/.test(textWithoutAge);
}

/**
 * Функция для удаления возраста из текста даты (если он есть)
 */
function removeAgeFromDate(dateText) {
  if (!dateText) return dateText;
  return dateText.replace(/\s*\(\d+\s+лет\)\s*$/, '').trim();
}

/**
 * Функция для расчёта возраста
 */
function calculateAge(birthDate, endDate = null) {
  if (!birthDate) return null;
  try {
    const birth = birthDate instanceof Date ? birthDate : new Date(birthDate);
    if (isNaN(birth.getTime())) return null;
    const end = endDate ? (endDate instanceof Date ? endDate : new Date(endDate)) : new Date();
    if (endDate && isNaN(end.getTime())) return null;
    let age = end.getFullYear() - birth.getFullYear();
    const monthDiff = end.getMonth() - birth.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && end.getDate() < birth.getDate())) {
      age--;
    }
    return age >= 0 ? age : null;
  } catch (e) {
    return null;
  }
}

/**
 * Функция для добавления возраста к дате (если возможно)
 */
function addAgeToDate(dateText, key, birthDate, deathDate = null) {
  if (!dateText) return dateText;
  
  // Убираем существующий возраст, если он есть
  const textWithoutAge = removeAgeFromDate(dateText);
  
  // Проверяем, есть ли год в дате
  if (!hasYearInDate(textWithoutAge)) {
    // Если года нет, не добавляем возраст
    return textWithoutAge;
  }
  
  // Если это дата рождения и есть дата смерти, не добавляем возраст
  if (key === 'Дата рождения' && deathDate) {
    return textWithoutAge;
  }
  
  // Если это дата смерти, используем дату смерти для расчета возраста на момент смерти
  if (key === 'Дата смерти' && birthDate && deathDate) {
    try {
      const birth = birthDate instanceof Date ? birthDate : new Date(birthDate);
      const death = deathDate instanceof Date ? deathDate : new Date(deathDate);
      if (!isNaN(birth.getTime()) && !isNaN(death.getTime())) {
        const ageAtDeath = calculateAge(birth, death);
        if (ageAtDeath !== null) {
          return `${textWithoutAge} (${ageAtDeath} лет)`;
        }
      }
    } catch (e) {
      // Игнорируем ошибку
    }
    return textWithoutAge;
  }
  
  // Для даты рождения без даты смерти - добавляем текущий возраст
  if (key === 'Дата рождения' && !deathDate) {
    // Пытаемся распарсить дату
    let dateForAge = null;
    if (birthDate) {
      try {
        dateForAge = birthDate instanceof Date ? birthDate : new Date(birthDate);
        if (isNaN(dateForAge.getTime())) {
          dateForAge = null;
        }
      } catch (e) {
        dateForAge = null;
      }
    }
    
    // Если не удалось получить дату из birthDate, пытаемся распарсить из текста
    if (!dateForAge) {
      dateForAge = parseDateFromText(textWithoutAge);
    }
    
    if (dateForAge) {
      const currentAge = calculateAge(dateForAge);
      if (currentAge !== null) {
        return `${textWithoutAge} (${currentAge} лет)`;
      }
    }
  }
  
  return textWithoutAge;
}

/**
 * Модуль таблицы фактов
 */
export function FactsTableModule({ data, moduleData, className = '' }) {
  const facts = data.facts || {};
  const title = moduleData?.title || 'Информация';
  const style = moduleData?.style || 'card';
  
  // Получаем даты из bio для расчета возраста
  const birthDate = data.bio?.birth_date || null;
  // Проверяем дату смерти в bio И в facts (может быть добавлена вручную)
  const deathDateFromBio = data.bio?.death_date || null;
  const deathDateFromFacts = facts['Дата смерти'] ? parseDateFromText(removeAgeFromDate(facts['Дата смерти'])) : null;
  const deathDate = deathDateFromBio || deathDateFromFacts;
  
  // Обрабатываем факты: добавляем возраст к датам
  const processedFacts = Object.entries(facts).reduce((acc, [key, value]) => {
    if (!value) return acc;
    
    let processedValue = value;
    
    // Если это дата рождения или дата смерти, добавляем возраст
    if (key === 'Дата рождения' || key === 'Дата смерти') {
      processedValue = addAgeToDate(value, key, birthDate, deathDate);
    }
    
    acc[key] = processedValue;
    return acc;
  }, {});
  
  const factEntries = Object.entries(processedFacts).filter(([_, v]) => v);
  
  if (factEntries.length === 0) return null;

  if (style === 'list') {
    return (
      <div className={className}>
        {title && <h3 className="font-semibold text-lg mb-3">{title}</h3>}
        <ul className="space-y-2">
          {factEntries.map(([key, value]) => (
            <li key={key} className="text-sm">
              <span className="text-muted-foreground">{key}:</span>{' '}
              <span dangerouslySetInnerHTML={{ __html: value }} />
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (style === 'table') {
    return (
      <div className={className}>
        {title && <h3 className="font-semibold text-lg mb-3">{title}</h3>}
        <table className="w-full text-sm">
          <tbody>
            {factEntries.map(([key, value]) => (
              <tr key={key} className="border-b">
                <td className="py-2 text-muted-foreground pr-4">{key}</td>
                <td className="py-2" dangerouslySetInnerHTML={{ __html: value }} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // Default: card style
  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {factEntries.map(([key, value]) => (
          <div key={key} className="flex justify-between text-sm">
            <span className="text-muted-foreground">{key}</span>
            <span className="font-medium text-right" dangerouslySetInnerHTML={{ __html: value }} />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

/**
 * Модуль рейтинга
 */
export function RatingWidgetModule({ data, moduleData, className = '' }) {
  const rating = data.rating || { average: 0, count: 0 };
  const title = moduleData?.title || 'Оценка';
  const style = moduleData?.style || 'smileys';
  
  if (style === 'numeric') {
    return (
      <Card className={className}>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center">
            <span className="text-4xl font-bold">{rating.average?.toFixed(1) || '0.0'}</span>
            <span className="text-muted-foreground">/10</span>
          </div>
          <p className="text-center text-sm text-muted-foreground mt-1">
            {rating.count || 0} голосов
          </p>
        </CardContent>
      </Card>
    );
  }

  if (style === 'stars') {
    const stars = Math.round(rating.average / 2);
    return (
      <Card className={className}>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex justify-center gap-1">
            {[1, 2, 3, 4, 5].map(i => (
              <span key={i} className={i <= stars ? 'text-yellow-500' : 'text-gray-300'}>★</span>
            ))}
          </div>
          <p className="text-center text-sm text-muted-foreground mt-1">
            {rating.average?.toFixed(1) || '0.0'}/10 ({rating.count || 0} голосов)
          </p>
        </CardContent>
      </Card>
    );
  }

  // Default: smileys (EmojiRating component)
  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <EmojiRating 
          rating={rating.average || 0} 
          count={rating.count || 0}
          interactive={false}
        />
      </CardContent>
    </Card>
  );
}

/**
 * Модуль тегов
 */
export function TagsCloudModule({ data, moduleData, className = '' }) {
  const tags = data.tags || [];
  const title = moduleData?.title;
  const style = moduleData?.style || 'badges';
  const maxTags = moduleData?.max_tags || 0;
  
  const displayTags = maxTags > 0 ? tags.slice(0, maxTags) : tags;
  
  if (displayTags.length === 0) return null;

  if (style === 'links') {
    return (
      <div className={className}>
        {title && <h3 className="font-semibold text-lg mb-3">{title}</h3>}
        <div className="flex flex-wrap gap-x-2 gap-y-1">
          {displayTags.map((tag, i) => (
            <Link 
              key={i} 
              to={`/tags/${encodeURIComponent(tag)}`}
              className="text-sm text-blue-600 hover:underline"
            >
              {tag}
            </Link>
          ))}
        </div>
      </div>
    );
  }

  if (style === 'cloud') {
    return (
      <div className={className}>
        {title && <h3 className="font-semibold text-lg mb-3">{title}</h3>}
        <div className="flex flex-wrap gap-2 justify-center">
          {displayTags.map((tag, i) => (
            <Link 
              key={i} 
              to={`/tags/${encodeURIComponent(tag)}`}
              className="text-sm px-2 py-1 bg-muted rounded hover:bg-muted/80"
              style={{ fontSize: `${Math.random() * 0.5 + 0.8}rem` }}
            >
              {tag}
            </Link>
          ))}
        </div>
      </div>
    );
  }

  // Default: badges
  return (
    <div className={className}>
      {title && <h3 className="font-semibold text-lg mb-3">{title}</h3>}
      <div className="flex flex-wrap gap-2">
        {displayTags.map((tag, i) => (
          <Link key={i} to={`/tags/${encodeURIComponent(tag)}`}>
            <Badge variant="secondary" className="hover:bg-secondary/80 cursor-pointer">
              {tag}
            </Badge>
          </Link>
        ))}
      </div>
    </div>
  );
}

/**
 * Модуль социальных ссылок
 */
export function SocialLinksModule({ data, moduleData, className = '' }) {
  const links = data.social_links || {};
  const title = moduleData?.title || 'Ссылки';
  const style = moduleData?.style || 'list';
  
  const linkEntries = Object.entries(links).filter(([_, url]) => url);
  
  if (linkEntries.length === 0) return null;

  const getLinkLabel = (key) => {
    const labels = {
      website: 'Официальный сайт',
      vk: 'ВКонтакте',
      telegram: 'Telegram',
      youtube: 'YouTube',
      instagram: 'Instagram',
      twitter: 'Twitter',
      tiktok: 'TikTok'
    };
    return labels[key] || key;
  };

  const getLinkIcon = (key) => {
    // Simple emoji icons
    const icons = {
      website: '🌐',
      vk: '💬',
      telegram: '📱',
      youtube: '▶️',
      instagram: '📷',
      twitter: '🐦',
      tiktok: '🎵'
    };
    return icons[key] || '🔗';
  };

  if (style === 'icons') {
    return (
      <div className={className}>
        {title && <h3 className="font-semibold text-lg mb-3">{title}</h3>}
        <div className="flex gap-3">
          {linkEntries.map(([key, url]) => (
            <a 
              key={key}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-2xl hover:opacity-70 transition-opacity"
              title={getLinkLabel(key)}
            >
              {getLinkIcon(key)}
            </a>
          ))}
        </div>
      </div>
    );
  }

  if (style === 'buttons') {
    return (
      <div className={className}>
        {title && <h3 className="font-semibold text-lg mb-3">{title}</h3>}
        <div className="flex flex-wrap gap-2">
          {linkEntries.map(([key, url]) => (
            <a 
              key={key}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90"
            >
              {getLinkIcon(key)} {getLinkLabel(key)}
            </a>
          ))}
        </div>
      </div>
    );
  }

  // Default: list
  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {linkEntries.map(([key, url]) => (
          <a 
            key={key}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between text-sm hover:text-blue-600"
          >
            <span>{getLinkLabel(key)}</span>
            <ExternalLink className="h-4 w-4" />
          </a>
        ))}
      </CardContent>
    </Card>
  );
}

/**
 * Рендерит системный модуль на основе его типа
 */
export function renderSystemModule(module, data, className = '') {
  const moduleData = module.data || {};
  
  switch (module.type) {
    case 'poster_photo':
      return <PosterPhotoModule key={module.id} data={data} moduleData={moduleData} className={className} />;
    case 'facts_table':
      return <FactsTableModule key={module.id} data={data} moduleData={moduleData} className={className} />;
    case 'rating_widget':
      return <RatingWidgetModule key={module.id} data={data} moduleData={moduleData} className={className} />;
    case 'tags_cloud':
      return <TagsCloudModule key={module.id} data={data} moduleData={moduleData} className={className} />;
    case 'social_links':
      return <SocialLinksModule key={module.id} data={data} moduleData={moduleData} className={className} />;
    default:
      return null;
  }
}

/**
 * Проверяет, является ли модуль системным (для сайдбара)
 */
export function isSystemModule(moduleType) {
  return ['poster_photo', 'facts_table', 'rating_widget', 'tags_cloud', 'social_links'].includes(moduleType);
}
