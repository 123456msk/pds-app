export function useFileSelection() {
  function isDicomLike(name = '') {
    const normalized = name.replaceAll('\\', '/');
    const baseName = normalized.split('/').pop() || '';
    const lower = baseName.toLowerCase();
    return (
      lower.endsWith('.dcm') ||
      lower.endsWith('.ima') ||
      /^\d+_\d+$/.test(baseName)
    );
  }

  function isZip(name = '') {
    return name.toLowerCase().endsWith('.zip');
  }

  function getDisplayPath(file) {
    return file.webkitRelativePath || file.name;
  }

  return {
    isDicomLike,
    isZip,
    getDisplayPath,
  };
}
