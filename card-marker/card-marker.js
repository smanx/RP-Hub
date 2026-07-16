const fs = require('fs');
const path = require('path');

const textDecoder = new TextDecoder('utf-8');
const textEncoder = new TextEncoder();

function readPngChunks(buffer) {
    const bytes = new Uint8Array(buffer);
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const chunks = {};
    let offset = 8;

    while (offset + 8 <= bytes.byteLength) {
        const length = view.getUint32(offset, false);
        const type = String.fromCharCode(
            view.getUint8(offset + 4),
            view.getUint8(offset + 5),
            view.getUint8(offset + 6),
            view.getUint8(offset + 7)
        );
        const dataStart = offset + 8;
        const dataEnd = dataStart + length;
        if (dataEnd + 4 > bytes.byteLength) break;

        const data = bytes.slice(dataStart, dataEnd);
        if (type === 'tEXt') {
            const splitIndex = data.indexOf(0);
            if (splitIndex !== -1) {
                const key = textDecoder.decode(data.slice(0, splitIndex));
                chunks[key] = textDecoder.decode(data.slice(splitIndex + 1));
            }
        } else if (type === 'iTXt') {
            let cursor = 0;
            while (cursor < data.length && data[cursor] !== 0) cursor += 1;
            const key = textDecoder.decode(data.slice(0, cursor));
            cursor += 1;
            if (cursor + 2 <= data.length) {
                const compressionFlag = data[cursor];
                cursor += 2;
                while (cursor < data.length && data[cursor] !== 0) cursor += 1;
                cursor += 1;
                while (cursor < data.length && data[cursor] !== 0) cursor += 1;
                cursor += 1;
                if (key && cursor < data.length && compressionFlag === 0) {
                    chunks[key] = textDecoder.decode(data.slice(cursor));
                }
            }
        }
        offset += 12 + length;
    }
    return chunks;
}

function findPngCharacterPayload(chunks) {
    if (chunks.chara) return chunks.chara;
    if (chunks.ccv3) return chunks.ccv3;
    return Object.values(chunks).find((value) => {
        const text = String(value || '').trim();
        return text.length > 50 && (text.startsWith('{') || text.startsWith('ey'));
    }) || '';
}

function decodeBase64Utf8(value) {
    try {
        const binary = atob(String(value || '').trim());
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i += 1) {
            bytes[i] = binary.charCodeAt(i);
        }
        return textDecoder.decode(bytes);
    } catch (_) {
        return String(value || '');
    }
}

function parseCharacterPayload(payload) {
    try {
        return JSON.parse(decodeBase64Utf8(payload));
    } catch (_) {
        return JSON.parse(String(payload || ''));
    }
}

function parsePngCharacterData(buffer) {
    const chunks = readPngChunks(buffer);
    const payload = findPngCharacterPayload(chunks);
    if (!payload) {
        const error = new Error('No character data found in PNG');
        error.chunks = chunks;
        throw error;
    }
    return {
        chunks,
        payload,
        data: parseCharacterPayload(payload)
    };
}

function encodeBase64Utf8(value) {
    const bytes = textEncoder.encode(String(value ?? ''));
    let binary = '';
    for (let i = 0; i < bytes.length; i += 1) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

const crc32Table = new Uint32Array(256);
for (let i = 0; i < 256; i += 1) {
    let c = i;
    for (let k = 0; k < 8; k += 1) {
        c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    }
    crc32Table[i] = c;
}

function crc32(bytes) {
    let crc = 0xFFFFFFFF;
    for (let i = 0; i < bytes.length; i += 1) {
        crc = (crc >>> 8) ^ crc32Table[(crc ^ bytes[i]) & 0xFF];
    }
    return (crc ^ 0xFFFFFFFF) >>> 0;
}

function createTextChunk(key, value) {
    const type = textEncoder.encode('tEXt');
    const keyData = textEncoder.encode(key);
    const valueData = textEncoder.encode(value);
    const chunkData = new Uint8Array(keyData.length + 1 + valueData.length);
    chunkData.set(keyData, 0);
    chunkData[keyData.length] = 0;
    chunkData.set(valueData, keyData.length + 1);

    const crcInput = new Uint8Array(type.length + chunkData.length);
    crcInput.set(type, 0);
    crcInput.set(chunkData, type.length);

    const fullChunk = new Uint8Array(12 + chunkData.length);
    const view = new DataView(fullChunk.buffer);
    view.setUint32(0, chunkData.length, false);
    fullChunk.set(type, 4);
    fullChunk.set(chunkData, 8);
    view.setUint32(8 + chunkData.length, crc32(crcInput), false);
    return fullChunk;
}

const PNG_SIGNATURE = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A];

function injectPngTextChunk(pngBuffer, key, value) {
    const pngBytes = new Uint8Array(pngBuffer);
    for (let i = 0; i < PNG_SIGNATURE.length; i += 1) {
        if (pngBytes[i] !== PNG_SIGNATURE[i]) {
            throw new Error('Invalid PNG: missing or wrong signature. Please restore the original file.');
        }
    }
    const view = new DataView(pngBytes.buffer, pngBytes.byteOffset, pngBytes.byteLength);
    const textChunk = createTextChunk(key, value);
    const removeTypes = new Set(['tEXt', 'iTXt', 'zTXt']);
    const kept = [pngBytes.slice(0, 8)];
    let offset = 8;

    while (offset + 8 <= pngBytes.byteLength) {
        const length = view.getUint32(offset, false);
        const type = String.fromCharCode(
            view.getUint8(offset + 4),
            view.getUint8(offset + 5),
            view.getUint8(offset + 6),
            view.getUint8(offset + 7)
        );
        const chunkEnd = offset + 12 + length;
        if (chunkEnd > pngBytes.byteLength) break;
        if (!removeTypes.has(type)) {
            kept.push(pngBytes.slice(offset, chunkEnd));
        }
        if (type === 'IHDR') {
            kept.push(textChunk);
        }
        offset = chunkEnd;
    }

    const totalLength = kept.reduce((sum, chunk) => sum + chunk.length, 0);
    const result = new Uint8Array(totalLength);
    let pos = 0;
    for (const chunk of kept) {
        result.set(chunk, pos);
        pos += chunk.length;
    }
    return result;
}

function extractJsonFromPng(pngPath) {
    const buffer = fs.readFileSync(pngPath);
    const result = parsePngCharacterData(buffer);
    const jsonPath = pngPath.replace(/\.png$/i, '.json');
    const jsonContent = JSON.stringify(result.data, null, 2);
    fs.writeFileSync(jsonPath, jsonContent, 'utf-8');
    console.log(`Extracted: ${pngPath} -> ${jsonPath}`);
    return result.data;
}

function injectJsonIntoPng(jsonPath) {
    const pngPath = jsonPath.replace(/\.json$/i, '.png');
    if (!fs.existsSync(pngPath)) {
        throw new Error(`PNG file not found: ${pngPath}`);
    }
    const pngBuffer = fs.readFileSync(pngPath);
    const jsonContent = fs.readFileSync(jsonPath, 'utf-8');
    const jsonData = JSON.parse(jsonContent);

    const data = jsonData.data || jsonData;
    if (!data.extensions || typeof data.extensions !== 'object') {
        data.extensions = {};
    }
    if (!data.extensions.rp_hub_watermark) {
        data.extensions.rp_hub_watermark = 'rp-hub';
    }

    const payload = encodeBase64Utf8(JSON.stringify(jsonData));
    const newPngBuffer = injectPngTextChunk(pngBuffer, 'chara', payload);
    fs.writeFileSync(jsonPath, JSON.stringify(jsonData, null, 2), 'utf-8');
    fs.writeFileSync(pngPath, newPngBuffer);
    console.log(`Injected: ${jsonPath} -> ${pngPath} (with rp-hub watermark)`);
}

function main() {
    const args = process.argv.slice(2);
    if (args.length === 0) {
        console.log('Usage:');
        console.log('  node card-marker.js <file.png>   - Extract JSON from PNG');
        console.log('  node card-marker.js <file.json>  - Inject JSON into PNG');
        process.exit(1);
    }

    const filePath = args[0];
    const ext = path.extname(filePath).toLowerCase();

    try {
        if (ext === '.png') {
            extractJsonFromPng(filePath);
        } else if (ext === '.json') {
            injectJsonIntoPng(filePath);
        } else {
            console.error('Error: File must be .png or .json');
            process.exit(1);
        }
    } catch (error) {
        console.error('Error:', error.message);
        if (error.chunks) {
            console.log('Available chunks:', Object.keys(error.chunks));
        }
        process.exit(1);
    }
}

main();