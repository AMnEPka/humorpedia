// Копия реестра backend/models/module_contract.json проверяется контрактным тестом.
import definitions from './moduleContract.json';

export const moduleContract = Object.fromEntries(definitions.map(item => [item.type, item]));
export const moduleNames = Object.fromEntries(definitions.map(item => [item.type, item.name]));
export const getAvailableModuleTypes = (contentType) => definitions
  .filter(item => item.for_types.includes(contentType))
  .map(item => item.type);
