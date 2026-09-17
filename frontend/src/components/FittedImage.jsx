/**
 * Показывает изображение целиком, не обрезая его под пропорции контейнера.
 * Свободное место остаётся нейтральным фоном: дублирующий `object-cover`
 * недопустим, потому что визуально снова обрезает фотографию.
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
