import { sharePage } from './share';

test('copies the page URL when system sharing is unavailable', async () => {
  const writeText = jest.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'share', { configurable: true, value: undefined });
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });

  await expect(sharePage('Команда')).resolves.toBe(true);
  expect(writeText).toHaveBeenCalledWith(window.location.href);
});

test('does not report a copied link after the native share sheet succeeds', async () => {
  const share = jest.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'share', { configurable: true, value: share });

  await expect(sharePage('Человек')).resolves.toBe(false);
  expect(share).toHaveBeenCalledWith({ title: 'Человек', url: window.location.href });
});
