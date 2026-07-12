// ==============================================
// 配置区域（环境变量优先级 > 代码默认值）
// ==============================================
const DEFAULT_TARGET_DOMAIN = 'https://rphforum.zeabur.app'
const INJECT_SCRIPT = true
// 环境变量REMOTE_JS_URL会覆盖这个默认值
const DEFAULT_REMOTE_JS_URL = "https://rp-hub.netlify.app/card-script.user.js"
// ==============================================

export default {
  async fetch(request, env, ctx) {
    // 优先使用环境变量，没有则使用默认值
    const REMOTE_JS_URL = env.REMOTE_JS_URL || DEFAULT_REMOTE_JS_URL
    
    const url = new URL(request.url)
    let targetUrl = url.searchParams.get('url')

    if (!targetUrl) {
      const u = new URL(DEFAULT_TARGET_DOMAIN)
      u.pathname = url.pathname
      u.search = url.search
      targetUrl = u.href
    }

    // 处理跨域预检请求
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': '*',
          'Access-Control-Allow-Headers': '*',
          'Access-Control-Max-Age': '86400'
        }
      })
    }

    // 请求目标页面
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body,
      redirect: 'follow'
    })

    // 处理响应头
    const headers = new Headers(response.headers)
    headers.set('Access-Control-Allow-Origin', '*')
    headers.set('Access-Control-Allow-Methods', '*')
    headers.set('Access-Control-Allow-Headers', '*')
    headers.delete('Content-Security-Policy')
    headers.delete('X-Frame-Options')

    const contentType = headers.get('content-type') || ''
    if (!contentType.includes('text/html') || !INJECT_SCRIPT) {
      return new Response(response.body, { status: response.status, headers })
    }

    // Worker下载JS代码并内嵌注入
    const html = await response.text()
    const jsRes = await fetch(REMOTE_JS_URL)
    const jsCode = await jsRes.text()
    const finalHtml = html + `<script>${jsCode}</script>`

    return new Response(finalHtml, {
      status: response.status,
      headers: headers
    })
  }
}