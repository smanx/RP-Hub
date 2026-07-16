const fs = require('fs');
const path = require('path');

const textDecoder = new TextDecoder('utf-8');

function readPngChunks(buffer) {
    const arrayBuffer = buffer instanceof ArrayBuffer ? buffer : buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
    const view = new DataView(arrayBuffer);
    const chunks = {};
    let offset = 8;

    while (offset < view.byteLength) {
        if (offset + 8 > view.byteLength) break;
        const length = view.getUint32(offset);
        const type = String.fromCharCode(
            view.getUint8(offset + 4),
            view.getUint8(offset + 5),
            view.getUint8(offset + 6),
            view.getUint8(offset + 7)
        );
        if (offset + 8 + length > view.byteLength) break;

        const data = new Uint8Array(arrayBuffer, offset + 8, length);
        if (type === 'tEXt') {
            const splitIndex = data.indexOf(0);
            if (splitIndex !== -1) {
                const key = textDecoder.decode(data.slice(0, splitIndex));
                const value = textDecoder.decode(data.slice(splitIndex + 1));
                chunks[key] = value;
            }
        } else if (type === 'iTXt') {
            let p = 0;
            while (p < data.length && data[p] !== 0) p++;
            const keyword = textDecoder.decode(data.slice(0, p));
            p++;
            if (p + 2 <= data.length) {
                const compressionFlag = data[p];
                p += 2;
                while (p < data.length && data[p] !== 0) p++;
                p++;
                while (p < data.length && data[p] !== 0) p++;
                p++;
                if (keyword && p < data.length && compressionFlag === 0) {
                    chunks[keyword] = textDecoder.decode(data.slice(p));
                }
            }
        }
        offset += 12 + length;
    }
    console.log('[DEBUG] Parsed text chunks, keys:', Object.keys(chunks));
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

function decodeBase64Utf8(str) {
    try {
        const binaryString = atob(str.trim());
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        return textDecoder.decode(bytes);
    } catch (_) {
        return str;
    }
}

function parseCharacterPayload(payload) {
    try {
        return JSON.parse(decodeBase64Utf8(payload));
    } catch (_) {
        return JSON.parse(String(payload || ''));
    }
}

function hasRpHubWatermark(charData) {
    const data = charData?.data || charData || {};
    const watermark = data.extensions?.rp_hub_watermark;
    return typeof watermark === 'string' && watermark.trim().toLowerCase() === 'rp-hub';
}

function checkPngFile(filePath) {
    const result = {
        file: filePath,
        isRpHub: false,
        hasCharacterData: false,
        error: null,
        characterName: null,
        spec: null
    };

    try {
        const buffer = fs.readFileSync(filePath);
        const chunks = readPngChunks(buffer);
        const payload = findPngCharacterPayload(chunks);

        if (!payload) {
            result.error = 'PNG 中未找到角色卡数据 (chara/ccv3 chunk)';
            return result;
        }

        result.hasCharacterData = true;
        const charData = parseCharacterPayload(payload);
        result.isRpHub = hasRpHubWatermark(charData);
        result.characterName = charData?.data?.name || charData?.name || charData?.char_name || '未知';
        result.spec = charData?.spec || charData?.data?.spec || 'unknown';

    } catch (e) {
        result.error = e.message;
    }
    return result;
}

function checkJsonFile(filePath) {
    const result = {
        file: filePath,
        isRpHub: false,
        hasCharacterData: false,
        error: null,
        characterName: null,
        spec: null
    };

    try {
        const content = fs.readFileSync(filePath, 'utf-8');
        const charData = JSON.parse(content);
        result.hasCharacterData = true;
        result.isRpHub = hasRpHubWatermark(charData);
        result.characterName = charData?.data?.name || charData?.name || charData?.char_name || '未知';
        result.spec = charData?.spec || charData?.data?.spec || 'unknown';
    } catch (e) {
        result.error = e.message;
    }
    return result;
}

function checkFile(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    if (ext === '.png') return checkPngFile(filePath);
    if (ext === '.json') return checkJsonFile(filePath);
    return { file: filePath, error: '不支持的文件类型，仅支持 .png 和 .json' };
}

function walkDirectory(dir, fileList = []) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            walkDirectory(fullPath, fileList);
        } else {
            const ext = path.extname(entry.name).toLowerCase();
            if (ext === '.png' || ext === '.json') {
                fileList.push(fullPath);
            }
        }
    }
    return fileList;
}

function formatResult(result) {
    const relPath = path.relative(process.cwd(), result.file);
    const status = result.error ? '❌ 错误' : (result.isRpHub ? '✅ RP-Hub' : '⚠️ 非 RP-Hub');
    const name = result.characterName ? ` | ${result.characterName}` : '';
    const spec = result.spec ? ` | ${result.spec}` : '';
    const error = result.error ? ` | ${result.error}` : '';
    return `${status}  ${relPath}${name}${spec}${error}`;
}

function main() {
    const args = process.argv.slice(2);
    const inputPath = args.length > 0
        ? path.resolve(args[0])
        : process.cwd();

    const stats = fs.existsSync(inputPath) ? fs.statSync(inputPath) : null;

    if (!stats) {
        console.error(`路径不存在: ${inputPath}`);
        process.exit(1);
    }

    let files = [];
    if (stats.isFile()) {
        files = [inputPath];
    } else if (stats.isDirectory()) {
        files = walkDirectory(inputPath);
        if (files.length === 0) {
            console.log('目录中未找到 .png 或 .json 文件');
            process.exit(0);
        }
    }

    console.log(`\n检测 ${files.length} 个文件...\n`);

    const results = files.map(checkFile);
    const rpHubCount = results.filter(r => r.isRpHub).length;
    const nonRpHubCount = results.filter(r => !r.error && !r.isRpHub).length;
    const errorCount = results.filter(r => r.error).length;

    results.forEach(r => console.log(formatResult(r)));

    console.log(`\n=== 统计 ===`);
    console.log(`总计: ${results.length}`);
    console.log(`✅ RP-Hub 卡片: ${rpHubCount}`);
    console.log(`⚠️ 非 RP-Hub 卡片: ${nonRpHubCount}`);
    console.log(`❌ 解析错误: ${errorCount}`);
}

main();