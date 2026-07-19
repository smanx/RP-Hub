// CF Worker: sta1n NovelAI proxy format → OpenAI standard format adapter
// 
// Input (unchanged from app):  GET /generate?tag=...&token=...&model=...&size=...&steps=...&...
// Converts to:                 POST {UPSTREAM}/v1/images/generations  (OpenAI standard)
// Returns raw image; on error, returns SVG with error message.
//
// Environment variables:
//   UPSTREAM_BASE - OpenAI-compatible API base URL (default: https://api.openai.com/v1)


export default {
  async fetch(request, env, ctx) {
    const DEFAULT_UPSTREAM = env.DEFAULT_UPSTREAM || 'https://openai.good.hidns.vip/v1';
    const DEFAULT_MODEL = env.DEFAULT_MODEL || 'qwen3.7-max';
    const DEFAULT_SIZE = env.DEFAULT_SIZE || '1:1';
    const MODEL_MAP = {
      'nai-diffusion-4-5-full': DEFAULT_MODEL,
    };

    const url = new URL(request.url);
    const upstreamBase = (env.UPSTREAM_BASE || DEFAULT_UPSTREAM).replace(/\/+$/, '');

    // CORS
    if (request.method === 'OPTIONS') {
      return cors(new Response(null, { status: 204 }));
    }

    // Only handle GET /generations (the format the app sends)
    if (url.pathname !== '/generations' || request.method !== 'GET') {
      return new Response('Not Found', { status: 404 });
    }

    // --- Extract params from sta1n-format query string ---
    const tag = url.searchParams.get('tag');
    const token = url.searchParams.get('token');
    const model = url.searchParams.get('model') || 'nai-diffusion-4-5-full';
    const size = url.searchParams.get('size') || '1024x1024';
    const artist = url.searchParams.get('artist') || '';
    const negative = url.searchParams.get('negative') || '';
    const steps = url.searchParams.get('steps');
    const scale = url.searchParams.get('scale');
    const sampler = url.searchParams.get('sampler');
    const noise_schedule = url.searchParams.get('noise_schedule');

    // Map model to OpenAI-compatible name
    const targetModel = MODEL_MAP[model] || MODEL_MAP;

    const headerMeta = {
      'X-Model': targetModel,
      'X-Size': DEFAULT_SIZE,
      'X-Response-Format': 'b64_json',
      'X-Upstream': maskUrl(DEFAULT_UPSTREAM),
    };

    if (!tag) {
      return errorSvg('Request Validation', 'Missing required parameter: "tag" (prompt)', headerMeta);
    }
    if (!token) {
      return errorSvg('Request Validation', 'Missing required parameter: "token" (API key)', headerMeta);
    }

    // Build prompt – prepend artist tags if provided
    let prompt = tag;
    if (artist) {
      prompt = `${artist}, ${prompt}`;
    }

    // Build negative prompt instruction if provided
    if (negative) {
      prompt += `\nNegative prompt: ${negative}`;
    }

    // --- Build OpenAI-format request ---
    const openaiBody = {
      model: targetModel,
      prompt: prompt,
      n: 1,
      size: DEFAULT_SIZE,
      response_format: 'b64_json',
    };

    let upstreamResponse;
    try {
      upstreamResponse = await fetch(`${upstreamBase}/images/generations`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(openaiBody),
      });
    } catch (e) {
      return errorSvg('Upstream Connection', `Connection failed: ${e.message}`, headerMeta);
    }

    // --- Handle upstream errors ---
    if (!upstreamResponse.ok) {
      let errText;
      try {
        const errJson = await upstreamResponse.json();
        errText = errJson.error?.message || JSON.stringify(errJson);
      } catch {
        try { errText = await upstreamResponse.text(); } catch { errText = `HTTP ${upstreamResponse.status}`; }
      }
      return errorSvg('Upstream API Error', errText, headerMeta);
    }

    // --- Parse OpenAI response ---
    let json;
    try {
      json = await upstreamResponse.json();
    } catch (e) {
      return errorSvg('Response Parsing', `Failed to parse upstream response: ${e.message}`, headerMeta);
    }

    const data = json.data?.[0];
    if (!data) {
      return errorSvg('Response Parsing', 'Upstream returned empty data array', headerMeta);
    }

    // Return b64_json directly as image
    if (data.b64_json) {
      const binary = Uint8Array.from(atob(data.b64_json), c => c.charCodeAt(0));
      return cors(new Response(binary, {
        headers: {
          'Content-Type': 'image/png',
          'Cache-Control': 'no-cache',
          ...headerMeta,
        },
      }));
    }

    // Fallback: if a URL is returned, fetch and relay it
    if (data.url) {
      let imgResponse;
      try {
        imgResponse = await fetch(data.url);
      } catch (e) {
        return errorSvg('Image Fetch', `Failed to fetch image URL: ${e.message}`, headerMeta);
      }
      if (!imgResponse.ok) {
        return errorSvg('Image Fetch', `Image URL returned HTTP ${imgResponse.status}`, headerMeta);
      }
      return cors(new Response(imgResponse.body, {
        headers: {
          'Content-Type': imgResponse.headers.get('Content-Type') || 'image/png',
          'Cache-Control': 'no-cache',
          ...headerMeta,
        },
      }));
    }

    return errorSvg('Response Parsing', 'Unknown response format from upstream', headerMeta);
  },
};

// --- Helpers ---

function cors(res) {
  const headers = new Headers(res.headers);
  headers.set('Access-Control-Allow-Origin', '*');
  headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  return new Response(res.body, { status: res.status, headers });
}

function errorSvg(step, message, extraHeaders = {}) {
  const escaped = message
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
  const escapedStep = step
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
  const lines = wrapText(escaped, 65);

  const fontSize = 15;
  const lineHeight = 22;
  const padding = 40;
  const headerHeight = 130;
  const textStartY = 220;
  const svgHeight = Math.max(400, textStartY + lines.length * lineHeight + padding);

  const textElements = lines.map((line, i) =>
    `    <text x="60" y="${textStartY + i * lineHeight}" font-family="monospace" font-size="${fontSize}" fill="#e0e0e0">${line}</text>`
  ).join('\n');

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="840" height="${svgHeight}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#1a1a2e"/>
      <stop offset="100%" style="stop-color:#16213e"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)"/>
  <rect x="40" y="40" width="760" height="${svgHeight - 80}" rx="14" fill="none" stroke="#e94560" stroke-width="2" opacity="0.8"/>
  <text x="420" y="${headerHeight}" font-family="monospace" font-size="26" fill="#e94560" text-anchor="middle" font-weight="bold">&#9888; Image Generation Error</text>
  <rect x="260" y="${headerHeight - 45}" width="320" height="32" rx="6" fill="#e94560" opacity="0.15"/>
  <text x="420" y="${headerHeight - 23}" font-family="monospace" font-size="15" fill="#ff8a8a" text-anchor="middle" font-weight="bold">Step: ${escapedStep}</text>
  <line x1="60" y1="${headerHeight + 20}" x2="780" y2="${headerHeight + 20}" stroke="#e94560" stroke-width="1" opacity="0.4"/>
${textElements}
</svg>`;

  return new Response(svg, {
    status: 200,
    headers: {
      'Content-Type': 'image/svg+xml',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'no-cache',
      ...extraHeaders,
    },
  });
}

function maskUrl(url) {
  try {
    const u = new URL(url);
    const parts = u.hostname.split('.');
    if (parts.length > 2) {
      for (let i = 0; i < parts.length - 2; i++) {
        parts[i] = 'x'.repeat(parts[i].length);
      }
      u.hostname = parts.join('.');
    }
    return u.origin + u.pathname;
  } catch {
    return url;
  }
}

function wrapText(text, maxLen) {
  if (text.length <= maxLen) return [text];
  const lines = [];
  while (text.length > maxLen) {
    let idx = text.lastIndexOf(' ', maxLen);
    if (idx === -1) idx = maxLen;
    lines.push(text.slice(0, idx));
    text = text.slice(idx).trim();
  }
  if (text) lines.push(text);
  return lines;
}
