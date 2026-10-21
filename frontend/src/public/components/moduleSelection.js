import { canPreviewModule, isSidebarModule } from '@/moduleContract';

// Filtering first preserves the existing TOC indices and stable ordering of ties.
export function selectVisibleModules(modules = []) {
  return (modules || []).filter(module => module.visible !== false)
    .sort((a, b) => (a.order || 0) - (b.order || 0));
}

export function selectPageModules(modules, { preview = false, excludeContent } = {}) {
  const sidebarModules = [];
  const contentModules = [];
  selectVisibleModules(modules).forEach(module => {
    if (preview && !canPreviewModule(module.type)) return;
    if (isSidebarModule(module.type)) sidebarModules.push(module);
    else if (!excludeContent?.(module)) contentModules.push(module);
  });
  return { sidebarModules, contentModules };
}
