// Backend JSON — единственный редактируемый реестр; frontend получает точную копию.
import definitions from './moduleContract.json';

export const moduleContract = Object.fromEntries(definitions.map(item => [item.type, item]));
export const moduleNames = Object.fromEntries(definitions.map(item => [item.type, item.name]));
export const getAvailableModuleTypes = (contentType) => definitions
  .filter(item => item.for_types.includes(contentType))
  .map(item => item.type);

export const isSidebarModule = (type) => moduleContract[type]?.rendering?.placement === 'sidebar';
export const isGenericModule = (type) => Object.prototype.hasOwnProperty.call(moduleContract, type)
  ? moduleContract[type].rendering?.owner === 'generic'
  : true;
export const canPreviewModule = (type) => moduleContract[type]?.rendering?.preview !== false;
