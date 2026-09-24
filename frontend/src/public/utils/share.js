export async function sharePage(title) {
  const url = window.location.href;
  if (typeof navigator.share === 'function') {
    try {
      await navigator.share({ title, url });
      return false;
    } catch (error) {
      if (error?.name === 'AbortError') return false;
    }
  }

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(url);
      return true;
    } catch {
      // Старые и ограниченные браузеры могут запретить Clipboard API.
    }
  }

  const input = document.createElement('textarea');
  input.value = url;
  input.setAttribute('readonly', '');
  input.style.position = 'fixed';
  input.style.opacity = '0';
  document.body.appendChild(input);
  input.select();
  try {
    if (!document.execCommand('copy')) throw new Error('Копирование недоступно');
    return true;
  } finally {
    input.remove();
  }
}
