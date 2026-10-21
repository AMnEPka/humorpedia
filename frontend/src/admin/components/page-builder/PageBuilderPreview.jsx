import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import PersonDetailPage from '@/public/pages/PersonDetailPage';
import TeamDetailPage from '@/public/pages/TeamDetailPage';
import ShowDetailPage from '@/public/pages/ShowDetailPage';

const EMPTY_ASSETS = [];
const ASSET_REFERENCE = /asset:([a-zA-Z0-9_-]+)/g;
const VIEWPORTS = {
  desktop: { label: 'Компьютер', width: 1120 },
  mobile: { label: 'Телефон', width: 390 },
};

export function usePrivateAssetUrls(ownerId, assets, getAsset) {
  const [urls, setUrls] = useState({});
  useEffect(() => {
    let active = true;
    const created = [];
    setUrls({});
    Promise.all((assets || []).map(async (asset) => {
      try {
        const response = await getAsset(ownerId, asset.id);
        const url = URL.createObjectURL(response.data);
        if (!active) {
          URL.revokeObjectURL(url);
          return [asset.id, ''];
        }
        created.push(url);
        return [asset.id, url];
      } catch {
        return [asset.id, ''];
      }
    })).then((entries) => { if (active) setUrls(Object.fromEntries(entries)); });
    return () => {
      active = false;
      created.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [ownerId, assets, getAsset]);
  return urls;
}

function copyPageStyles(targetDocument) {
  const elements = document.head.querySelectorAll('style, link[rel~="stylesheet"]');
  elements.forEach((element) => {
    const copy = element.cloneNode(true);
    if (copy.tagName === 'LINK') copy.href = element.href;
    targetDocument.head.appendChild(copy);
  });
  targetDocument.documentElement.className = document.documentElement.className;
  targetDocument.documentElement.lang = document.documentElement.lang || 'ru';
  targetDocument.body.style.margin = '0';
}

function renderPublicPage(kind, page, ownerId, relations) {
  if (kind === 'person') {
    page._id = ownerId;
    return <PersonDetailPage preview previewDocument={page} previewRelations={relations} />;
  }
  if (kind === 'team') {
    page._id = ownerId;
    return <TeamDetailPage preview previewDocument={page} previewRelations={relations} />;
  }
  return <ShowDetailPage preview previewDocument={page} previewRelations={relations} />;
}

export default function PageBuilderPreview({ kind, page, assets = EMPTY_ASSETS, ownerId, getAsset, relations = [] }) {
  const iframeRef = useRef(null);
  const [viewport, setViewport] = useState('desktop');
  const [portalTarget, setPortalTarget] = useState(null);
  const assetUrls = usePrivateAssetUrls(ownerId, assets, getAsset);

  const previewPage = useMemo(() => {
    const resolveAssets = (value) => {
      if (typeof value === 'string') {
        return value.replace(ASSET_REFERENCE, (reference, assetId) => assetUrls[assetId] || reference);
      }
      if (Array.isArray(value)) return value.map(resolveAssets);
      if (value && typeof value === 'object') {
        return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, resolveAssets(item)]));
      }
      return value;
    };
    return resolveAssets(page || {});
  }, [page, assetUrls]);

  const onFrameLoad = useCallback(() => {
    const frameDocument = iframeRef.current?.contentDocument;
    if (!frameDocument) return;
    copyPageStyles(frameDocument);
    setPortalTarget(frameDocument.getElementById('page-preview-root'));
  }, []);

  const baseHref = typeof window === 'undefined' ? '/' : `${window.location.origin}/`;
  const iframeSrcDoc = `<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><base href="${baseHref}"></head><body><div id="page-preview-root"></div></body></html>`;

  return (
    <section aria-label="Предпросмотр страницы" className="space-y-3">
      <div role="group" aria-label="Размер предпросмотра" className="flex gap-2">
        {Object.entries(VIEWPORTS).map(([key, option]) => (
          <button
            key={key}
            type="button"
            aria-pressed={viewport === key}
            className={`rounded border px-3 py-2 ${viewport === key ? 'border-primary bg-primary text-primary-foreground' : 'bg-white'}`}
            onClick={() => setViewport(key)}
          >
            {option.label}
          </button>
        ))}
      </div>
      <div className="w-full overflow-x-auto border bg-slate-100">
        <iframe
          ref={iframeRef}
          title={`Предпросмотр страницы: ${VIEWPORTS[viewport].label.toLowerCase()}`}
          sandbox="allow-same-origin"
          srcDoc={iframeSrcDoc}
          onLoad={onFrameLoad}
          style={{ display: 'block', width: `${VIEWPORTS[viewport].width}px`, height: '650px', border: 0, background: '#fff' }}
        />
      </div>
      {portalTarget && createPortal(renderPublicPage(kind, previewPage, ownerId, relations), portalTarget)}
    </section>
  );
}
