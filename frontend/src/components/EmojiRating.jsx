/**
 * EmojiRating Component
 * 
 * Полноценный компонент рейтинга с поддержкой эмодзи или изображений.
 * Поддерживает дробные значения, интерактивный выбор, кастомизацию стилей.
 * 
 * ============================================================================
 * КАСТОМИЗАЦИЯ:
 * ============================================================================
 * 
 * 1. ЭМОДЗИ - передайте массив emojis длиной max:
 *    emojis={['😡','😠','😟','😕','😐','🙂','😊','😃','😄','🤩']}
 * 
 * 2. ИЗОБРАЖЕНИЯ - передайте массив images вместо emojis:
 *    images={['/rating/1.png', '/rating/2.png', ... '/rating/10.png']}
 *    
 *    Требования к изображениям:
 *    - Формат: PNG или SVG (с прозрачным фоном)
 *    - Размер: 64x64px или 128x128px (квадратные)
 *    - Соотношение сторон: 1:1
 * 
 * 3. ЦВЕТА - настройте через пропсы или CSS-переменные:
 *    filledColor="#ffcc00"   // Цвет активной части
 *    emptyColor="#cccccc"    // Цвет неактивной части
 *    hoverColor="#ff9900"    // Цвет при наведении
 *    borderColor="#888888"   // Цвет рамки
 * 
 * 4. РАЗМЕР - укажите size в пикселях:
 *    size={32}  // Размер эмодзи/изображения
 * 
 * 5. ШАГ - укажите step для точности дробных значений:
 *    step={0.1}   // Значения 4.1, 4.2, 4.3...
 *    step={0.25}  // Значения 4.0, 4.25, 4.5, 4.75...
 *    step={0.5}   // Значения 4.0, 4.5, 5.0...
 * 
 * ============================================================================
 */

import { useState, useRef, useCallback } from 'react';

// Дефолтные эмодзи от грустного к весёлому
const DEFAULT_EMOJIS = ['😡', '😠', '😟', '😕', '😐', '🙂', '😊', '😃', '😄', '🤩'];

/**
 * @param {Object} props
 * @param {number} [props.value] - Текущее значение рейтинга (может быть дробным: 4.5, 7.8)
 * @param {(value: number) => void} [props.onChange] - Колбэк при выборе нового рейтинга
 * @param {number} [props.max=10] - Количество позиций рейтинга
 * @param {string[]} [props.emojis] - Массив эмодзи длиной max
 * @param {string[]} [props.images] - Массив URL изображений (альтернатива emojis)
 * @param {boolean} [props.readOnly=false] - Только отображение, без интерактивности
 * @param {number} [props.step=0.1] - Минимальный шаг дробного значения
 * @param {number} [props.size=28] - Размер эмодзи в пикселях
 * @param {string} [props.className] - Дополнительный CSS-класс
 * @param {string} [props.filledColor='#ffcc00'] - Цвет активной части
 * @param {string} [props.emptyColor='#9ca3af'] - Цвет неактивной части
 * @param {string} [props.hoverColor='#fbbf24'] - Цвет при наведении
 * @param {string} [props.borderColor] - Цвет рамки
 * @param {boolean} [props.showValue=true] - Показывать числовое значение
 * @param {string} [props.valueFormat] - Формат отображения: 'fraction' (4.5/10), 'decimal' (4.5), 'percent' (45%)
 * @param {number} [props.count] - Количество оценок для отображения
 */
export default function EmojiRating({
  value: externalValue,
  onChange,
  max = 10,
  emojis: customEmojis,
  images,
  readOnly = false,
  step = 0.1,
  size = 28,
  className = '',
  filledColor = '#ffcc00',
  emptyColor = '#9ca3af',
  hoverColor = '#fbbf24',
  borderColor,
  showValue = true,
  valueFormat = 'fraction',
  count,
}) {
  // Внутреннее состояние для неконтролируемого режима
  const [internalValue, setInternalValue] = useState(0);
  const [hoverValue, setHoverValue] = useState(null);
  const containerRef = useRef(null);

  // Используем внешнее или внутреннее значение
  const value = externalValue !== undefined ? externalValue : internalValue;
  
  // Значение для отображения (hover имеет приоритет)
  const displayValue = hoverValue !== null ? hoverValue : value;

  // Подготовка массива эмодзи/изображений
  const items = images || customEmojis || DEFAULT_EMOJIS;
  const effectiveMax = Math.min(max, items.length);

  /**
   * Вычисляет значение рейтинга на основе позиции курсора
   */
  const calculateValueFromEvent = useCallback((event, position) => {
    const target = event.currentTarget;
    const rect = target.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const percentage = Math.max(0, Math.min(1, x / rect.width));
    
    // Базовое значение = позиция - 1 + процент внутри элемента
    const rawValue = (position - 1) + percentage;
    
    // Округляем до шага
    const steppedValue = Math.round(rawValue / step) * step;
    
    // Ограничиваем диапазон
    return Math.max(step, Math.min(effectiveMax, steppedValue));
  }, [step, effectiveMax]);

  /**
   * Обработчик движения мыши
   */
  const handleMouseMove = useCallback((event, position) => {
    if (readOnly) return;
    const newValue = calculateValueFromEvent(event, position);
    setHoverValue(newValue);
  }, [readOnly, calculateValueFromEvent]);

  /**
   * Обработчик ухода мыши
   */
  const handleMouseLeave = useCallback(() => {
    setHoverValue(null);
  }, []);

  /**
   * Обработчик клика
   */
  const handleClick = useCallback((event, position) => {
    if (readOnly) return;
    const newValue = calculateValueFromEvent(event, position);
    
    // Обновляем внутреннее состояние
    setInternalValue(newValue);
    
    // Вызываем колбэк
    if (onChange) {
      onChange(newValue);
    }
  }, [readOnly, calculateValueFromEvent, onChange]);

  /**
   * Вычисляет процент заполнения для позиции
   */
  const getFillPercentage = (position) => {
    if (displayValue >= position) {
      return 100;
    }
    if (displayValue <= position - 1) {
      return 0;
    }
    // Частичное заполнение
    return (displayValue - (position - 1)) * 100;
  };

  /**
   * Форматирует значение для отображения
   */
  const formatValue = (val) => {
    const formatted = val.toFixed(1);
    switch (valueFormat) {
      case 'decimal':
        return formatted;
      case 'percent':
        return `${Math.round((val / effectiveMax) * 100)}%`;
      case 'fraction':
      default:
        return `${formatted} / ${effectiveMax}`;
    }
  };

  /**
   * Форматирует количество оценок
   */
  const formatCount = (num) => {
    if (!num) return '';
    const lastTwo = num % 100;
    const lastOne = num % 10;
    
    if (lastTwo >= 11 && lastTwo <= 14) {
      return `${num} оценок`;
    }
    if (lastOne === 1) {
      return `${num} оценка`;
    }
    if (lastOne >= 2 && lastOne <= 4) {
      return `${num} оценки`;
    }
    return `${num} оценок`;
  };

  // CSS переменные для кастомизации
  const cssVariables = {
    '--emoji-rating-size': `${size}px`,
    '--emoji-rating-filled': filledColor,
    '--emoji-rating-empty': emptyColor,
    '--emoji-rating-hover': hoverColor,
    '--emoji-rating-border': borderColor || 'transparent',
  };

  return (
    <div 
      ref={containerRef}
      className={`emoji-rating ${readOnly ? 'emoji-rating--readonly' : ''} ${className}`}
      style={cssVariables}
      onMouseLeave={handleMouseLeave}
    >
      {/* Шкала эмодзи */}
      <div className="emoji-rating__scale">
        {Array.from({ length: effectiveMax }).map((_, index) => {
          const position = index + 1;
          const fillPercentage = getFillPercentage(position);
          const isHovered = hoverValue !== null && hoverValue >= position - 0.5;
          const item = items[index];
          const isImage = images && images.length > 0;

          return (
            <div
              key={position}
              className={`emoji-rating__item ${isHovered ? 'emoji-rating__item--hovered' : ''}`}
              onMouseMove={(e) => handleMouseMove(e, position)}
              onClick={(e) => handleClick(e, position)}
              style={{ 
                width: size, 
                height: size,
                cursor: readOnly ? 'default' : 'pointer'
              }}
            >
              {/* Фоновый слой (пустой/серый) */}
              <div className="emoji-rating__layer emoji-rating__layer--background">
                {isImage ? (
                  <img src={item} alt={`Rating ${position}`} style={{ width: size, height: size }} />
                ) : (
                  <span style={{ fontSize: size * 0.85 }}>{item}</span>
                )}
              </div>
              
              {/* Передний слой (заполненный) */}
              <div 
                className="emoji-rating__layer emoji-rating__layer--foreground"
                style={{ width: `${fillPercentage}%` }}
              >
                {isImage ? (
                  <img src={item} alt={`Rating ${position}`} style={{ width: size, height: size }} />
                ) : (
                  <span style={{ fontSize: size * 0.85 }}>{item}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Текстовое значение */}
      {showValue && (
        <div className="emoji-rating__value">
          <span className="emoji-rating__number">{formatValue(displayValue)}</span>
          {count !== undefined && (
            <>
              <span className="emoji-rating__separator"> • </span>
              <span className="emoji-rating__count">{formatCount(count)}</span>
            </>
          )}
        </div>
      )}

      {/* Стили компонента */}
      <style>{`
        .emoji-rating {
          display: inline-flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;
          user-select: none;
        }

        .emoji-rating__scale {
          display: flex;
          gap: 2px;
        }

        .emoji-rating__item {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 4px;
          border: 1px solid var(--emoji-rating-border);
          overflow: hidden;
          transition: transform 0.15s ease, box-shadow 0.15s ease;
        }

        .emoji-rating:not(.emoji-rating--readonly) .emoji-rating__item:hover {
          transform: scale(1.15);
          z-index: 1;
        }

        .emoji-rating__item--hovered {
          box-shadow: 0 0 8px var(--emoji-rating-hover);
        }

        .emoji-rating__layer {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
        }

        .emoji-rating__layer--background {
          filter: grayscale(100%) opacity(0.4);
        }

        .emoji-rating__layer--foreground {
          filter: none;
          overflow: hidden;
        }

        .emoji-rating__layer--foreground span,
        .emoji-rating__layer--foreground img {
          position: absolute;
          left: 0;
        }

        .emoji-rating__layer img {
          object-fit: contain;
        }

        .emoji-rating__value {
          font-size: 14px;
          color: #6b7280;
          white-space: nowrap;
        }

        .emoji-rating__number {
          font-weight: 600;
          color: #374151;
        }

        .emoji-rating__separator {
          color: #d1d5db;
        }

        .emoji-rating__count {
          color: #9ca3af;
        }

        /* Readonly state */
        .emoji-rating--readonly .emoji-rating__item {
          cursor: default;
        }
        
        .emoji-rating--readonly .emoji-rating__item:hover {
          transform: none;
        }
      `}</style>
    </div>
  );
}

/**
 * ============================================================================
 * ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:
 * ============================================================================
 * 
 * 1. Базовое использование с эмодзи:
 * 
 * function App() {
 *   const [rating, setRating] = useState(4.8);
 *   return (
 *     <EmojiRating
 *       value={rating}
 *       onChange={setRating}
 *     />
 *   );
 * }
 * 
 * 2. Кастомные эмодзи:
 * 
 * <EmojiRating
 *   value={7.5}
 *   emojis={['💀','😵','😩','😢','😐','🙂','😊','😁','🥰','❤️']}
 * />
 * 
 * 3. С изображениями:
 * 
 * <EmojiRating
 *   value={6.3}
 *   images={[
 *     '/img/rating/face-1.png',
 *     '/img/rating/face-2.png',
 *     // ... до 10 изображений
 *   ]}
 *   size={40}
 * />
 * 
 * 4. Только для отображения (readOnly):
 * 
 * <EmojiRating
 *   value={4.5}
 *   readOnly
 *   count={42}
 * />
 * 
 * 5. Полная кастомизация:
 * 
 * <EmojiRating
 *   value={rating}
 *   onChange={setRating}
 *   max={10}
 *   step={0.25}
 *   size={32}
 *   emojis={['😡','😠','😟','😕','😐','🙂','😊','😃','😄','🤩']}
 *   filledColor="#ffcc00"
 *   emptyColor="#cccccc"
 *   hoverColor="#ff9900"
 *   borderColor="#e5e7eb"
 *   showValue={true}
 *   valueFormat="fraction"
 *   count={156}
 * />
 * 
 * ============================================================================
 */
