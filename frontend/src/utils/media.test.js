import { contentImageUrl, mediaUrl, personPhotoUrl } from './media';

test('preserves private blob URLs from page-builder previews', () => {
  const privatePreviewUrl = 'blob:http://localhost:3000/preview-image-id';

  expect(mediaUrl(privatePreviewUrl)).toBe(privatePreviewUrl);
  expect(contentImageUrl({ slug: 'person' }, { url: privatePreviewUrl })).toBe(privatePreviewUrl);
  expect(personPhotoUrl({ photo: { url: privatePreviewUrl } })).toBe(privatePreviewUrl);
});
