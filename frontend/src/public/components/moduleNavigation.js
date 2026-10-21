// A public page may be rendered into the constructor's iframe through a portal.
export function scrollToModule(event, id) {
  const target = event.currentTarget.ownerDocument.getElementById(id);
  target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
