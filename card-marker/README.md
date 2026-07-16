# Card Marker 使用文档

## 目录结构
```
card-marker/
├── card-marker.js      # 双向转换脚本（PNG ↔ JSON）
├── cards/              # 角色卡目录
│   ├── ShyCousin/
│   │   └── Shy Cousin.png
│   └── ShyCousin2/
│       └── Shy Cousin2.png
└── README.md           # 本文档
```

## 核心原理

角色卡数据以 **Base64 编码** 存储在 PNG 图片的 **tEXt / iTXt 文本块** 中，键名为 `chara`（兼容 `ccv3`）。

### PNG 文本块结构
```
PNG Signature (8 bytes)
IHDR chunk
tEXt chunk: key="chara", value=<Base64(JSON)>
... 其他 chunks ...
IEND chunk
```

## 判断是否为 RP-Hub 卡片

### 方法：检查 `extensions.rp_hub_watermark` 字段

```javascript
const hasRpHubWatermark = (charData) => {
    const data = charData?.data || charData || {};
    const watermark = data.extensions?.rp_hub_watermark;
    return typeof watermark === 'string' && watermark.trim().toLowerCase() === 'rp-hub';
};
```

**要求**：
- JSON 根对象或 `data` 子对象下必须有 `extensions.rp_hub_watermark`
- 值必须为字符串 `"rp-hub"`（不区分大小写、忽略首尾空格）

**示例通过的 JSON**：
```json
{
  "data": {
    "name": "角色名",
    "extensions": {
      "rp_hub_watermark": "rp-hub"
    }
  },
  "spec": "chara_card_v2"
}
```

## 使用脚本 `card-marker.js`

### 1. PNG → JSON（提取角色卡数据）
```bash
node card-marker.js "cards/ShyCousin/Shy Cousin.png"
```
输出：同目录生成 `Shy Cousin.json`

### 2. JSON → PNG（写入角色卡数据）
```bash
node card-marker.js "cards/ShyCousin/Shy Cousin.json"
```
- 读取同名 PNG（必须存在）
- 将 JSON Base64 编码后注入 `chara` tEXt 块（插在 IHDR 之后）
- 覆盖原 PNG 文件

## 代码实现细节

### 读取 PNG 文本块
```javascript
function readPngChunks(buffer) {
    const view = new DataView(buffer);
    const chunks = {};
    let offset = 8; // 跳过 PNG 签名
    
    while (offset < view.byteLength) {
        const length = view.getUint32(offset);
        const type = String.fromCharCode(
            view.getUint8(offset + 4),
            view.getUint8(offset + 5),
            view.getUint8(offset + 6),
            view.getUint8(offset + 7)
        );
        const data = new Uint8Array(buffer, offset + 8, length);
        
        if (type === 'tEXt') {
            // 格式: key\0value
            const splitIndex = data.indexOf(0);
            if (splitIndex !== -1) {
                const key = new TextDecoder().decode(data.slice(0, splitIndex));
                const value = new TextDecoder().decode(data.slice(splitIndex + 1));
                chunks[key] = value;
            }
        } else if (type === 'iTXt') {
            // 国际化文本块，解析更复杂
            // ... 解析逻辑
        }
        
        offset += 12 + length; // Length(4) + Type(4) + Data + CRC(4)
    }
    return chunks;
}
```

### 查找角色卡载荷
```javascript
function findPngCharacterPayload(chunks) {
    if (chunks.chara) return chunks.chara;      // 标准键名
    if (chunks.ccv3) return chunks.ccv3;        // 兼容键名
    // 兜底：找第一个看起来像 Base64/JSON 的大文本块
    return Object.values(chunks).find(v => 
        v.length > 50 && (v.startsWith('{') || v.startsWith('ey'))
    ) || '';
}
```

### Base64 解码（UTF-8 安全）
```javascript
function decodeBase64Utf8(str) {
    const binaryString = atob(str.trim());
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return new TextDecoder('utf-8').decode(bytes);
}
```

### 注入 tEXt 块
```javascript
function injectPngTextChunk(pngBuffer, key, value) {
    const pngBytes = new Uint8Array(pngBuffer);
    const view = new DataView(pngBytes.buffer);
    
    // 1. 创建 tEXt chunk
    const type = new TextEncoder().encode('tEXt');
    const keyData = new TextEncoder().encode(key);
    const valueData = new TextEncoder().encode(value);
    const chunkData = new Uint8Array(keyData.length + 1 + valueData.length);
    chunkData.set(keyData, 0);
    chunkData[keyData.length] = 0;  // 分隔符
    chunkData.set(valueData, keyData.length + 1);
    
    // 2. 计算 CRC32
    const crcInput = new Uint8Array(type.length + chunkData.length);
    crcInput.set(type, 0);
    crcInput.set(chunkData, type.length);
    const crc = crc32(crcInput);
    
    // 3. 组装完整 chunk
    const fullChunk = new Uint8Array(12 + chunkData.length);
    new DataView(fullChunk.buffer).setUint32(0, chunkData.length, false);
    fullChunk.set(type, 4);
    fullChunk.set(chunkData, 8);
    new DataView(fullChunk.buffer).setUint32(8 + chunkData.length, crc, false);
    
    // 4. 找到 IHDR 后的插入位置
    let insertPos = 33, offset = 8;
    while (offset + 8 <= pngBytes.byteLength) {
        const length = view.getUint32(offset, false);
        const typeStr = String.fromCharCode(...new Uint8Array(pngBytes.buffer, offset + 4, 4));
        if (typeStr === 'IHDR') { insertPos = offset + 12 + length; break; }
        offset += 12 + length;
    }
    
    // 5. 重组 PNG
    const result = new Uint8Array(pngBytes.length + fullChunk.length);
    result.set(pngBytes.slice(0, insertPos), 0);
    result.set(fullChunk, insertPos);
    result.set(pngBytes.slice(insertPos), insertPos + fullChunk.length);
    return result;
}
```

## 常见问题

### Q: 提取出的 JSON 解析报错
**原因**：某些卡片的 `chara` 值未 Base64 编码，直接是明文 JSON。
**解决**：`parseCharacterPayload` 已做双重尝试：
```javascript
try { return JSON.parse(decodeBase64Utf8(payload)); }
catch { return JSON.parse(payload); }
```

### Q: 写入后图片无法预览
**原因**：注入位置不对或 CRC 校验失败。
**检查**：
1. 确保在 IHDR chunk 之后插入
2. CRC32 计算包含 `type + chunkData`
3. PNG 结构完整性（IEND chunk 保留）

### Q: 如何批量处理
```bash
# 提取所有 PNG
find cards -name "*.png" -exec node card-marker.js {} \;

# 写入所有 JSON（需同名 PNG 存在）
find cards -name "*.json" -exec node card-marker.js {} \;
```

## 相关文件
- `card-marker.js` - 完整可运行脚本
- `cards/**/*.png` - 源角色卡图片
- `cards/**/*.json` - 提取/编辑后的 JSON 数据