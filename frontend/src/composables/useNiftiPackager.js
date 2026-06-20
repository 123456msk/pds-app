import dicomParser from 'dicom-parser';
import JSZip from 'jszip';
import { gzip } from 'pako';

const UNCOMPRESSED_TRANSFER_SYNTAXES = new Set([
  '',
  '1.2.840.10008.1.2',
  '1.2.840.10008.1.2.1',
  '1.2.840.10008.1.2.2',
]);

function readString(dataSet, tag) {
  return (dataSet.string(tag) || '').trim();
}

function readNumber(dataSet, tag, fallback = 0) {
  const rawValue = readString(dataSet, tag);
  if (rawValue === '') return fallback;
  const value = Number(rawValue);
  return Number.isFinite(value) ? value : fallback;
}

function readNumberList(dataSet, tag) {
  return readString(dataSet, tag)
    .split('\\')
    .map(Number)
    .filter(Number.isFinite);
}

function getBaseName(path = '') {
  return path.replaceAll('\\', '/').split('/').pop() || '';
}

export function parseLeadingFileIndex(path) {
  const name = getBaseName(path);
  const match = name.match(/^(\d+)/);
  return match ? Number(match[1]) : null;
}

function isInsideClosedRange(index, range) {
  return index !== null && index >= range.start && index <= range.end;
}

function cross(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function dot(a, b) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function parseSlice(entry) {
  const byteArray = new Uint8Array(entry.buffer);
  const dataSet = dicomParser.parseDicom(byteArray);
  const transferSyntax = readString(dataSet, 'x00020010');

  if (!UNCOMPRESSED_TRANSFER_SYNTAXES.has(transferSyntax)) {
    throw new Error(`${getBaseName(entry.path)} 使用压缩 DICOM (${transferSyntax})，浏览器调试打包暂不支持。`);
  }

  const pixelElement = dataSet.elements.x7fe00010;
  if (!pixelElement || pixelElement.encapsulatedPixelData) {
    throw new Error(`${getBaseName(entry.path)} 没有可直接读取的未压缩像素数据。`);
  }

  const rows = dataSet.uint16('x00280010');
  const cols = dataSet.uint16('x00280011');
  const samples = dataSet.uint16('x00280002') || 1;
  const bitsAllocated = dataSet.uint16('x00280100') || 16;
  const pixelRepresentation = dataSet.uint16('x00280103') || 0;
  const frameCount = readNumber(dataSet, 'x00280008', 1);
  const photometricInterpretation = readString(dataSet, 'x00280004') || 'UNKNOWN';

  if (!rows || !cols || samples !== 1 || frameCount !== 1 || ![8, 16, 32].includes(bitsAllocated)) {
    throw new Error(
      `${getBaseName(entry.path)} 的像素格式暂不支持：` +
      `Rows=${rows || 0}, Columns=${cols || 0}, SamplesPerPixel=${samples}, ` +
      `NumberOfFrames=${frameCount}, BitsAllocated=${bitsAllocated}, ` +
      `PhotometricInterpretation=${photometricInterpretation}。`,
    );
  }

  const littleEndian = transferSyntax !== '1.2.840.10008.1.2.2';
  const pixelCount = rows * cols;
  const bytesPerPixel = bitsAllocated / 8;
  const requiredBytes = pixelCount * bytesPerPixel;
  if (pixelElement.length < requiredBytes) {
    throw new Error(`${getBaseName(entry.path)} 的像素数据长度不足。`);
  }

  const view = new DataView(byteArray.buffer, byteArray.byteOffset + pixelElement.dataOffset, requiredBytes);
  const slope = readNumber(dataSet, 'x00281053', 1);
  const intercept = readNumber(dataSet, 'x00281052', 0);
  const pixels = new Float32Array(pixelCount);

  for (let i = 0; i < pixelCount; i += 1) {
    const offset = i * bytesPerPixel;
    let raw;
    if (bitsAllocated === 8) {
      raw = pixelRepresentation ? view.getInt8(offset) : view.getUint8(offset);
    } else if (bitsAllocated === 16) {
      raw = pixelRepresentation
        ? view.getInt16(offset, littleEndian)
        : view.getUint16(offset, littleEndian);
    } else {
      raw = pixelRepresentation
        ? view.getInt32(offset, littleEndian)
        : view.getUint32(offset, littleEndian);
    }
    pixels[i] = raw * slope + intercept;
  }

  const position = readNumberList(dataSet, 'x00200032');
  const orientation = readNumberList(dataSet, 'x00200037');
  const pixelSpacing = readNumberList(dataSet, 'x00280030');
  const rowDirection = orientation.length === 6 ? orientation.slice(0, 3) : [1, 0, 0];
  const columnDirection = orientation.length === 6 ? orientation.slice(3, 6) : [0, 1, 0];
  const normal = cross(rowDirection, columnDirection);
  const sliceLocation = position.length === 3
    ? dot(position, normal)
    : readNumber(dataSet, 'x00201041', entry.metadata.instanceNumber);

  return {
    path: entry.path,
    fileIndex: parseLeadingFileIndex(entry.path),
    rows,
    cols,
    pixels,
    position: position.length === 3 ? position : [0, 0, sliceLocation],
    rowDirection,
    columnDirection,
    normal,
    rowSpacing: pixelSpacing[0] || 1,
    columnSpacing: pixelSpacing[1] || 1,
    sliceThickness: readNumber(dataSet, 'x00180050', 1),
    sliceLocation,
  };
}

function buildNiftiBytes(slices) {
  if (!slices.length) throw new Error('筛选范围内没有 DICOM 切片。');

  const sorted = [...slices].sort((a, b) => {
    if (a.sliceLocation !== b.sliceLocation) return a.sliceLocation - b.sliceLocation;
    return a.fileIndex - b.fileIndex;
  });
  const first = sorted[0];

  for (const slice of sorted) {
    if (slice.rows !== first.rows || slice.cols !== first.cols) {
      throw new Error('同一序列中的 DICOM 图像尺寸不一致。');
    }
  }

  let sliceSpacing = first.sliceThickness || 1;
  if (sorted.length > 1) {
    const distances = [];
    for (let i = 1; i < sorted.length; i += 1) {
      const distance = Math.abs(sorted[i].sliceLocation - sorted[i - 1].sliceLocation);
      if (distance > 0) distances.push(distance);
    }
    if (distances.length) {
      distances.sort((a, b) => a - b);
      sliceSpacing = distances[Math.floor(distances.length / 2)];
    }
  }

  const voxelCount = first.cols * first.rows * sorted.length;
  const output = new ArrayBuffer(352 + voxelCount * 4);
  const view = new DataView(output);
  const bytes = new Uint8Array(output);
  const littleEndian = true;

  view.setInt32(0, 348, littleEndian);
  view.setInt16(40, 3, littleEndian);
  view.setInt16(42, first.cols, littleEndian);
  view.setInt16(44, first.rows, littleEndian);
  view.setInt16(46, sorted.length, littleEndian);
  view.setInt16(48, 1, littleEndian);
  view.setInt16(50, 1, littleEndian);
  view.setInt16(52, 1, littleEndian);
  view.setInt16(54, 1, littleEndian);
  view.setInt16(70, 16, littleEndian);
  view.setInt16(72, 32, littleEndian);
  view.setFloat32(76, 1, littleEndian);
  view.setFloat32(80, first.columnSpacing, littleEndian);
  view.setFloat32(84, first.rowSpacing, littleEndian);
  view.setFloat32(88, sliceSpacing, littleEndian);
  view.setFloat32(108, 352, littleEndian);
  view.setFloat32(112, 1, littleEndian);
  bytes[123] = 2;
  view.setInt16(254, 1, littleEndian);

  const ras = (value, axis) => (axis < 2 ? -value : value);
  const origin = first.position;
  const xAxis = first.rowDirection.map((value, axis) => ras(value * first.columnSpacing, axis));
  const yAxis = first.columnDirection.map((value, axis) => ras(value * first.rowSpacing, axis));
  const zAxis = first.normal.map((value, axis) => ras(value * sliceSpacing, axis));
  const rasOrigin = origin.map((value, axis) => ras(value, axis));

  for (let axis = 0; axis < 3; axis += 1) {
    const rowOffset = 280 + axis * 16;
    view.setFloat32(rowOffset, xAxis[axis], littleEndian);
    view.setFloat32(rowOffset + 4, yAxis[axis], littleEndian);
    view.setFloat32(rowOffset + 8, zAxis[axis], littleEndian);
    view.setFloat32(rowOffset + 12, rasOrigin[axis], littleEndian);
  }

  bytes.set([110, 43, 49, 0], 344);
  const dataView = new DataView(output, 352);
  let voxelOffset = 0;
  for (const slice of sorted) {
    for (let i = 0; i < slice.pixels.length; i += 1) {
      dataView.setFloat32(voxelOffset * 4, slice.pixels[i], littleEndian);
      voxelOffset += 1;
    }
  }

  return {
    bytes: new Uint8Array(output),
    dimensions: [first.cols, first.rows, sorted.length],
    spacing: [first.columnSpacing, first.rowSpacing, sliceSpacing],
    indices: sorted.map((slice) => slice.fileIndex),
  };
}

function selectEntries(state, seriesUid, range) {
  return state.dicomEntries
    .filter((entry) => entry.metadata.seriesUid === seriesUid)
    .filter((entry) => isInsideClosedRange(parseLeadingFileIndex(entry.path), range));
}

function yieldToBrowser() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

async function buildModality(name, state, series, range, onProgress) {
  if (!series) throw new Error(`未识别到 ${name.toUpperCase()} 序列。`);
  const entries = selectEntries(state, series.uid, range);
  if (!entries.length) {
    throw new Error(`${name.toUpperCase()} 在闭区间 [${range.start}, ${range.end}] 内没有匹配文件。`);
  }

  const displayName = name.toUpperCase();
  onProgress?.(`正在读取 ${displayName} DICOM（0/${entries.length}）`);
  const slices = [];
  for (let index = 0; index < entries.length; index += 1) {
    slices.push(parseSlice(entries[index]));
    if ((index + 1) % 4 === 0 || index === entries.length - 1) {
      onProgress?.(`正在读取 ${displayName} DICOM（${index + 1}/${entries.length}）`);
      await yieldToBrowser();
    }
  }

  onProgress?.(`正在构建 ${name}.nii.gz`);
  await yieldToBrowser();
  const nifti = buildNiftiBytes(slices);
  onProgress?.(`正在压缩 ${name}.nii.gz`);
  await yieldToBrowser();
  const compressed = gzip(nifti.bytes);
  await yieldToBrowser();

  return {
    name,
    fileName: `${name}.nii.gz`,
    compressed,
    dimensions: nifti.dimensions,
    spacing: nifti.spacing,
    indices: nifti.indices,
    sourceSeriesUid: series.uid,
    sourceDescription: series.description,
  };
}

export function useNiftiPackager() {
  async function buildDebugPackage(modalities, ranges, onProgress) {
    const outputs = [];
    outputs.push(await buildModality('mri', modalities.mri, modalities.mri.selectedSeries, ranges.mri, onProgress));
    outputs.push(await buildModality('ct', modalities.pet, modalities.pet.ctSeries, ranges.psma, onProgress));
    outputs.push(await buildModality('pet', modalities.pet, modalities.pet.selectedSeries, ranges.psma, onProgress));

    const manifest = {
      createdAt: new Date().toISOString(),
      rangeRule: '闭区间；文件名按第一个数字解析，例如 1_0.dcm → 1',
      ranges,
      files: outputs.map(({ compressed, ...item }) => ({
        ...item,
        compressedBytes: compressed.byteLength,
      })),
    };

    const zip = new JSZip();
    for (const output of outputs) {
      zip.file(output.fileName, output.compressed);
    }
    zip.file('manifest.json', JSON.stringify(manifest, null, 2));

    onProgress?.('正在生成调试 ZIP');
    await yieldToBrowser();
    return {
      blob: await zip.generateAsync(
        { type: 'blob', compression: 'DEFLATE' },
        (metadata) => onProgress?.(`正在生成调试 ZIP（${Math.round(metadata.percent)}%）`),
      ),
      manifest,
    };
  }

  return { buildDebugPackage };
}
