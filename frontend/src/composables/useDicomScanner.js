import dicomParser from 'dicom-parser';
import JSZip from 'jszip';
import { useFileSelection } from './useFileSelection';

const { isDicomLike, isZip, getDisplayPath } = useFileSelection();

function readTag(dataSet, tag) {
  return (dataSet.string(tag) || '').trim();
}

function normalizeText(value) {
  return String(value || '').toLowerCase();
}

function shouldMatchSeries(type, metadata) {
  const modality = normalizeText(metadata.modality).toUpperCase();
  const text = [
    metadata.seriesDescription,
    metadata.protocolName,
    metadata.sequenceName,
    metadata.imageType,
  ]
    .map(normalizeText)
    .join(' | ');

  if (type === 'mri') {
    return (
      modality === 'MR' &&
      (text.includes('t2') || text.includes('tse')) &&
      !text.includes('sag') &&
      !text.includes('cor')
    );
  }

  return modality === 'PT' || modality === 'PET';
}

function shouldKeepCtSeries(metadata) {
  return normalizeText(metadata.modality).toUpperCase() === 'CT';
}

function parseDicomEntry(entry, index, type) {
  const dataSet = dicomParser.parseDicom(new Uint8Array(entry.buffer));
  const metadata = {
    modality: readTag(dataSet, 'x00080060').toUpperCase(),
    seriesDescription: readTag(dataSet, 'x0008103e') || '(no description)',
    protocolName: readTag(dataSet, 'x00181030'),
    sequenceName: readTag(dataSet, 'x00180024'),
    imageType: readTag(dataSet, 'x00080008'),
    seriesUid: readTag(dataSet, 'x0020000e') || `series_${index}`,
    instanceNumber: Number(readTag(dataSet, 'x00200013')) || 0,
  };

  return {
    ...entry,
    metadata,
    matches: shouldMatchSeries(type, metadata),
    keepCt: type === 'pet' && shouldKeepCtSeries(metadata),
  };
}

async function extractEntriesFromZip(file) {
  const zip = await JSZip.loadAsync(file);
  const entries = [];

  for (const [path, fileObject] of Object.entries(zip.files)) {
    if (fileObject.dir || path.startsWith('__MACOSX')) continue;
    if (!isDicomLike(path)) continue;

    entries.push({
      source: file.name,
      path,
      buffer: await fileObject.async('arraybuffer'),
    });
  }

  return entries;
}

async function extractEntriesFromFiles(files) {
  const entries = [];
  let zipCount = 0;

  for (const file of files) {
    const path = getDisplayPath(file);
    if (isZip(file.name)) {
      zipCount += 1;
      entries.push(...(await extractEntriesFromZip(file)));
    } else if (isDicomLike(file.name)) {
      entries.push({
        source: file.name,
        path,
        buffer: await file.arrayBuffer(),
      });
    }
  }

  return { entries, zipCount };
}

function buildSeries(parsedEntries) {
  const groups = new Map();

  for (const entry of parsedEntries) {
    const uid = entry.metadata.seriesUid;
    if (!groups.has(uid)) {
      groups.set(uid, {
        uid,
        modality: entry.metadata.modality,
        description: entry.metadata.seriesDescription,
        protocolName: entry.metadata.protocolName,
        sequenceName: entry.metadata.sequenceName,
        imageType: entry.metadata.imageType,
        count: 0,
        matches: entry.matches,
        keepCt: entry.keepCt,
        files: [],
      });
    }

    const group = groups.get(uid);
    group.count += 1;
    group.matches = group.matches || entry.matches;
    group.keepCt = group.keepCt || entry.keepCt;
    group.files.push({
      path: entry.path,
      source: entry.source,
    });
  }

  const series = Array.from(groups.values());
  const selectedSeries =
    series
      .filter((item) => item.matches)
      .sort((a, b) => b.count - a.count)[0] || null;
  const ctSeries =
    series
      .filter((item) => item.keepCt)
      .sort((a, b) => b.count - a.count)[0] || null;

  return { series, selectedSeries, ctSeries };
}

export function useDicomScanner() {
  async function scanFiles(type, files) {
    const { entries, zipCount } = await extractEntriesFromFiles(files);
    const parsedEntries = [];
    const errors = [];

    for (let index = 0; index < entries.length; index += 1) {
      try {
        parsedEntries.push(parseDicomEntry(entries[index], index, type));
      } catch (error) {
        errors.push({
          path: entries[index].path,
          message: error.message || 'DICOM 解析失败',
        });
      }
    }

    const { series, selectedSeries, ctSeries } = buildSeries(parsedEntries);

    return {
      fileCount: files.length,
      zipCount,
      dicomCount: parsedEntries.length,
      skippedCount: errors.length,
      series,
      selectedSeries,
      ctSeries,
      dicomEntries: parsedEntries,
      errors,
    };
  }

  return {
    scanFiles,
  };
}
