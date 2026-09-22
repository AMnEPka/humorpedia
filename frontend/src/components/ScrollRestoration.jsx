import { useEffect, useRef } from 'react';
import { useLocation, useNavigationType } from 'react-router-dom';


const RESTORE_RETRY_INTERVAL_MS = 100;
const RESTORE_TIMEOUT_MS = 10000;
const USER_SCROLL_EVENTS = ['wheel', 'touchstart', 'pointerdown', 'keydown'];


function getStorageKey(location) {
  const entryKey = location.key || 'default';
  const url = `${location.pathname}${location.search}${location.hash}`;
  return `scroll:${entryKey}:${url}`;
}


function readScrollPosition(storageKey) {
  try {
    const stored = window.sessionStorage.getItem(storageKey);
    if (stored === null) return null;

    const y = Number(stored);
    return Number.isFinite(y) && y >= 0 ? y : null;
  } catch {
    return null;
  }
}


function saveScrollPosition(storageKey) {
  try {
    const y = window.scrollY ?? window.pageYOffset ?? 0;
    window.sessionStorage.setItem(storageKey, String(y));
  } catch {
    // sessionStorage can be unavailable in restricted or private browsing modes.
  }
}


function restoreScrollPosition(targetY) {
  let intervalId;
  let timeoutId;
  let cancelled = false;

  const stop = () => {
    if (cancelled) return;
    cancelled = true;
    window.clearInterval(intervalId);
    window.clearTimeout(timeoutId);
    USER_SCROLL_EVENTS.forEach((eventName) => {
      window.removeEventListener(eventName, stop);
    });
  };

  const tryRestore = () => {
    if (cancelled) return;

    window.scrollTo(0, targetY);
    const currentY = window.scrollY ?? window.pageYOffset ?? 0;
    if (Math.abs(currentY - targetY) <= 1) {
      stop();
    }
  };

  USER_SCROLL_EVENTS.forEach((eventName) => {
    window.addEventListener(eventName, stop, { passive: true });
  });

  tryRestore();
  if (!cancelled) {
    intervalId = window.setInterval(tryRestore, RESTORE_RETRY_INTERVAL_MS);
    timeoutId = window.setTimeout(stop, RESTORE_TIMEOUT_MS);
  }

  return stop;
}


export default function ScrollRestoration() {
  const location = useLocation();
  const navigationType = useNavigationType();
  const storageKey = getStorageKey(location);
  const currentStorageKeyRef = useRef(storageKey);
  currentStorageKeyRef.current = storageKey;

  useEffect(() => {
    if (typeof window === 'undefined' || !window.history) return undefined;

    const previousValue = window.history.scrollRestoration;
    try {
      window.history.scrollRestoration = 'manual';
    } catch {
      return undefined;
    }

    return () => {
      try {
        window.history.scrollRestoration = previousValue;
      } catch {
        // The History API can be restricted in embedded browser contexts.
      }
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    let cancelRestore = () => {};

    if (navigationType === 'POP') {
      const storedY = readScrollPosition(storageKey);
      if (storedY !== null) {
        cancelRestore = restoreScrollPosition(storedY);
      }
    } else {
      window.scrollTo(0, 0);
    }

    const saveCurrentPosition = () => saveScrollPosition(storageKey);
    window.addEventListener('beforeunload', saveCurrentPosition);

    return () => {
      cancelRestore();
      // React StrictMode performs an extra setup/cleanup cycle in development.
      // Save only when the history entry really changes; full-page exits are
      // covered by beforeunload.
      if (currentStorageKeyRef.current !== storageKey) {
        saveCurrentPosition();
      }
      window.removeEventListener('beforeunload', saveCurrentPosition);
    };
  }, [storageKey, navigationType]);

  return null;
}
