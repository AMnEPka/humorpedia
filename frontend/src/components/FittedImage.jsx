/**
 * Показывает изображение целиком, не обрезая его под пропорции контейнера.
 * Для фотографий свободное место заполняется мягким фоном из того же изображения,
 * для логотипов остаётся нейтральный фон с внутренним отступом.
 */
export default function FittedImage({
  src,
  alt = '',
  className = '',
  imageClassName = '',
  mode = 'photo',
  loading = 'lazy',
  fallbackKey,
  fit = 'contain',
}) {
  const isLogo = mode === 'logo';
  const fallbackSrc = placeholderImageUrl(fallbackKey || alt || src);
  const [displaySrc, setDisplaySrc] = useState(src || fallbackSrc);

  useEffect(() => setDisplaySrc(src || fallbackSrc), [src, fallbackSrc]);

  const handleError = () => {
    if (displaySrc !== fallbackSrc) setDisplaySrc(fallbackSrc);
  };

  return (
    <div
      className={`relative isolate overflow-hidden ${isLogo ? 'bg-white' : 'bg-slate-100'} ${className}`}
    >
      {!isLogo && (
        <>
          <img
            src={displaySrc}
            alt=""
            aria-hidden="true"
            className="absolute inset-0 h-full w-full scale-150 object-cover blur-3xl opacity-55 saturate-50"
          />
          <div className="absolute inset-0 bg-white/35" aria-hidden="true" />
        </>
      )}
      <img
        src={displaySrc}
        alt={alt}
        loading={loading}
        onError={handleError}
        className={`relative z-10 h-full w-full ${fit === 'cover' ? 'object-cover' : 'object-contain'} ${isLogo ? 'p-2' : ''} ${imageClassName}`}
      />
    </div>
  );
}
import { useEffect, useState } from 'react';
import { placeholderImageUrl } from '@/utils/media';
