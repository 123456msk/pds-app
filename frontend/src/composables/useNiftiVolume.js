import pako from 'pako';
import { downloadResultArrayBuffer } from '../api/casePreparation';

function readValue(view, offset, datatype, littleEndian) {
  switch (datatype) {
    case 2: return view.getUint8(offset);
    case 4: return view.getInt16(offset, littleEndian);
    case 8: return view.getInt32(offset, littleEndian);
    case 16: return view.getFloat32(offset, littleEndian);
    case 64: return view.getFloat64(offset, littleEndian);
    case 256: return view.getInt8(offset);
    case 512: return view.getUint16(offset, littleEndian);
    case 768: return view.getUint32(offset, littleEndian);
    default: throw new Error(`暂不支持 NIfTI datatype ${datatype}`);
  }
}

export function parseNiftiBuffer(input, compressed = true) {
  let bytes = new Uint8Array(input);
  if (compressed) bytes = pako.inflate(bytes);
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  const view = new DataView(buffer);
  let littleEndian = true;
  let headerSize = view.getInt32(0, littleEndian);
  if (headerSize !== 348 && headerSize !== 540) {
    littleEndian = false;
    headerSize = view.getInt32(0, littleEndian);
  }
  if (headerSize !== 348) throw new Error('当前阅片器仅支持 NIfTI-1。');

  const dimensions = Array.from({ length: 8 }, (_, index) => view.getInt16(40 + index * 2, littleEndian));
  const nx = dimensions[1];
  const ny = dimensions[2];
  const nz = dimensions[3];
  const datatype = view.getInt16(70, littleEndian);
  const bitsPerVoxel = view.getInt16(72, littleEndian);
  const voxelOffset = Math.floor(view.getFloat32(108, littleEndian));
  let slope = view.getFloat32(112, littleEndian);
  const intercept = view.getFloat32(116, littleEndian);
  if (!slope) slope = 1;
  const bytesPerVoxel = bitsPerVoxel / 8;
  const voxelCount = nx * ny * nz;
  const data = new Float32Array(voxelCount);
  for (let index = 0; index < voxelCount; index += 1) {
    data[index] = readValue(view, voxelOffset + index * bytesPerVoxel, datatype, littleEndian) * slope + intercept;
  }
  return { dimensions: [nx, ny, nz], data };
}

export async function loadNifti(url) {
  const response = { ok: true, arrayBuffer: async () => downloadResultArrayBuffer(url) };
  if (!response.ok) throw new Error(`读取结果文件失败：${response.status}`);
  return parseNiftiBuffer(await response.arrayBuffer(), url.toLowerCase().endsWith('.gz'));
}
