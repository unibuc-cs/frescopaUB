import { getConfigValue } from './configs.js';

// Endpoint configuration functions
function getAEMPublish() {
  return getConfigValue('aem.publish');
}

function getAEMAuthor() {
  return getConfigValue('aem.author');
}

export { getAEMPublish, getAEMAuthor };
