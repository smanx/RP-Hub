#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RP-Hub 构建脚本
用于下载远程资源到本地并添加 PWA 支持
可以在本地运行或被 GitHub Actions 调用
"""

import os
import sys
import time
import hashlib
import shutil
import urllib.request
from pathlib import Path


class Colors:
    """终端颜色输出"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_info(message: str) -> None:
    """打印信息"""
    print(f"{Colors.CYAN}{message}{Colors.ENDC}")


def print_success(message: str) -> None:
    """打印成功消息"""
    print(f"{Colors.GREEN}{message}{Colors.ENDC}")


def print_warning(message: str) -> None:
    """打印警告消息"""
    print(f"{Colors.YELLOW}{message}{Colors.ENDC}")


def print_error(message: str) -> None:
    """打印错误消息"""
    print(f"{Colors.RED}{message}{Colors.ENDC}")


def calculate_file_hash(file_path: str, length: int = 8) -> str:
    """计算文件的 hash 值"""
    hash_obj = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()[:length]


def get_hashed_filename(file_path: str) -> tuple:
    """获取包含 hash 的文件名"""
    path = Path(file_path)
    file_hash = calculate_file_hash(str(path))
    new_name = f"{path.stem}.{file_hash}{path.suffix}"
    return str(path.parent / new_name), file_hash


def download_file(urls: list, dest_path: str, name: str) -> str:
    """下载文件到指定路径，支持多个备用源，返回文件 hash"""
    if isinstance(urls, str):
        urls = [urls]
    
    print(f"  - 正在下载 {name}...")
    for i, url in enumerate(urls):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response, open(dest_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            
            if os.path.exists(dest_path):
                size = os.path.getsize(dest_path)
                file_hash = calculate_file_hash(dest_path)
                print_success(f"    ✓ {name} 下载成功 ({size / 1024:.1f} KB) - hash: {file_hash}")
                return file_hash
        except Exception as e:
            if i < len(urls) - 1:
                print_warning(f"    备用源 {i+1} 失败，尝试下一个...")
            else:
                print_error(f"    ✗ {name} 下载失败: {e}")
    return ""


def replace_in_file(file_path: str, replacements: dict) -> None:
    """替换文件中的内容，模式未匹配时只打警告不中断构建"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    modified = False
    for old_str, new_str in replacements.items():
        if old_str in content:
            content = content.replace(old_str, new_str)
            modified = True
        else:
            print_warning(f"    ⚠ 替换模式未匹配，跳过: {old_str[:60]}...")
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)


def replace_domain_in_files(directory: Path, old_domain: str, new_domain: str) -> None:
    """递归替换目录中所有文件的域名"""
    file_extensions = ['.html', '.css', '.js', '.json', '.md', '.txt']
    
    for file_path in directory.rglob('*'):
        if file_path.is_file() and any(file_path.name.lower().endswith(ext) for ext in file_extensions):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if old_domain in content:
                    new_content = content.replace(old_domain, new_domain)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"    → 替换: {file_path.relative_to(directory.parent)}")
            except Exception as e:
                print_warning(f"    ⚠ 跳过文件 {file_path}: {e}")


def generate_manifest_json(output_path: str, icon_path: str) -> None:
    """生成 manifest.json 文件"""
    manifest_content = '''{
  "name": "Roleplay Hub",
  "short_name": "RP Hub",
  "description": "一款纯前端运行的本地角色扮演（Roleplay）对话和角色卡生成工具",
  "start_url": "./",
  "display": "standalone",
  "background_color": "#f9fafb",
  "theme_color": "#1f2937",
  "icons": [
    {
      "src": "ICON_PATH",
      "sizes": "any",
      "type": "image/svg+xml",
      "purpose": "any maskable"
    }
  ]
}'''.replace("ICON_PATH", icon_path)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(manifest_content)
    print_success("  ✓ manifest.json 生成成功")


def generate_sw_js(output_path: str, version: str, cache_urls: list) -> None:
    """生成 Service Worker 文件"""
    sw_content = '''const CACHE_NAME = 'rp-hub-VERSION';
const urlsToCache = CACHE_URLS;

const HTML_FILES = ['/', '/index.html', '/character/index.html'];

function isHtmlFile(pathname) {
    return HTML_FILES.some(html => pathname === html || pathname.endsWith('/index.html') || pathname === '/');
}

// 从旧缓存中复制未变化的资源（排除 HTML 文件）
async function copyFromOldCache(newCache) {
    const cacheNames = await caches.keys();
    const oldCaches = cacheNames.filter(name => name !== CACHE_NAME && name.startsWith('rp-hub-'));
    
    let copiedCount = 0;
    
    for (const oldCacheName of oldCaches) {
        const oldCache = await caches.open(oldCacheName);
        const oldKeys = await oldCache.keys();
        
        for (const request of oldKeys) {
            const requestUrl = new URL(request.url);
            
            if (isHtmlFile(requestUrl.pathname)) {
                console.log('[ServiceWorker] Skipping HTML file (will fetch fresh):', requestUrl.pathname);
                continue;
            }
            
            const relativePath = requestUrl.pathname.substring(requestUrl.pathname.lastIndexOf('/') + 1);
            
            const urlInNewCache = urlsToCache.some(url => {
                const urlPath = url.split('?')[0];
                const urlFilename = urlPath.substring(urlPath.lastIndexOf('/') + 1);
                return urlFilename === relativePath;
            });
            
            if (urlInNewCache) {
                try {
                    const response = await oldCache.match(request);
                    if (response) {
                        await newCache.put(request, response.clone());
                        copiedCount++;
                        console.log('[ServiceWorker] Copied from old cache:', requestUrl.pathname);
                    }
                } catch (e) {
                    console.log('[ServiceWorker] Failed to copy:', requestUrl.pathname, e);
                }
            }
        }
    }
    
    return copiedCount;
}

// 安装阶段：缓存所有资源
self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Installing new version:', 'VERSION');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(async (newCache) => {
                console.log('[ServiceWorker] Checking old caches for reusable resources...');
                const copiedCount = await copyFromOldCache(newCache);
                console.log('[ServiceWorker] Copied', copiedCount, 'resources from old cache');
                
                const cachedKeys = await newCache.keys();
                const cachedUrls = new Set(cachedKeys.map(req => {
                    const url = new URL(req.url);
                    return url.pathname;
                }));
                
                const urlsToDownload = [];
                for (const url of urlsToCache) {
                    let fullUrl;
                    if (url.startsWith('http')) {
                        fullUrl = new URL(url);
                    } else {
                        fullUrl = new URL(url, self.location.href);
                    }
                    
                    if (!cachedUrls.has(fullUrl.pathname)) {
                        urlsToDownload.push(url);
                    } else {
                        console.log('[ServiceWorker] Skipping (already in cache):', url);
                    }
                }
                
                console.log('[ServiceWorker] Need to download', urlsToDownload.length, 'new resources');
                
                if (urlsToDownload.length > 0) {
                    return Promise.all(
                        urlsToDownload.map(url => {
                            const request = new Request(url, {
                                cache: 'reload',
                                mode: 'no-cors'
                            });
                            return fetch(request).then(response => {
                                if (response && response.ok) {
                                    newCache.put(request, response.clone());
                                    console.log('[ServiceWorker] Downloaded:', url);
                                }
                                return response;
                            }).catch(e => {
                                console.log('[ServiceWorker] Failed to download:', url, e);
                            });
                        })
                    );
                }
            })
            .then(() => {
                console.log('[ServiceWorker] Skip waiting for activation');
                return self.skipWaiting();
            })
    );
});

// 激活阶段：清理旧缓存
self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activating new version:', 'VERSION');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME && cacheName.startsWith('rp-hub-')) {
                        console.log('[ServiceWorker] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('[ServiceWorker] Claiming all clients');
            return self.clients.claim();
        })
    );
});

// 拦截请求 - 只缓存我们的静态资源
self.addEventListener('fetch', (event) => {
    const request = event.request;
    const requestUrl = new URL(request.url);
    
    // 只处理 http/https 请求
    if (!requestUrl.protocol.startsWith('http')) {
        return;
    }
    
    // 只缓存 GET 请求
    if (request.method !== 'GET') {
        console.log('[ServiceWorker] Skip non-GET request:', request.method, requestUrl.pathname);
        event.respondWith(fetch(request));
        return;
    }
    
    const pathname = requestUrl.pathname;
    
    // HTML 文件使用 network-first 策略，确保总是获取最新版本
    if (isHtmlFile(pathname)) {
        console.log('[ServiceWorker] HTML file, using network-first:', pathname);
        event.respondWith(
            fetch(request)
                .then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(request, responseToCache);
                        });
                    }
                    return networkResponse;
                })
                .catch(() => {
                    console.log('[ServiceWorker] Network failed, falling back to cache:', pathname);
                    return caches.match(request, { ignoreSearch: true });
                })
        );
        return;
    }
    
    // 检查是否在我们的预缓存列表中
    const isInPrecacheList = urlsToCache.some(url => {
        let cacheUrl;
        if (url.startsWith('http')) {
            cacheUrl = new URL(url);
        } else {
            cacheUrl = new URL(url, self.location.href);
        }
        return cacheUrl.pathname === requestUrl.pathname;
    });
    
    // 检查是否是我们项目目录下的静态文件
    const isProjectResource = 
        pathname.includes('/assets/') || 
        pathname.endsWith('/manifest.json') ||
        pathname.endsWith('/sw.js');
    
    // 如果是我们的资源，使用缓存策略
    if (isInPrecacheList || isProjectResource) {
        event.respondWith(
            caches.match(request, { ignoreSearch: true })
                .then((cachedResponse) => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    
                    return fetch(request).then((networkResponse) => {
                        if (!networkResponse || networkResponse.status !== 200) {
                            return networkResponse;
                        }
                        
                        const responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(request, responseToCache);
                        });
                        return networkResponse;
                    }).catch(() => {
                        return caches.match(request, { ignoreSearch: true });
                    });
                })
        );
    } else {
        console.log('[ServiceWorker] Skip cache for:', requestUrl.pathname);
        event.respondWith(fetch(request));
    }
});

// 监听来自客户端的消息
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        console.log('[ServiceWorker] Received SKIP_WAITING message');
        self.skipWaiting();
    }
});'''
    sw_content = sw_content.replace('VERSION', version)
    sw_content = sw_content.replace('CACHE_URLS', str(cache_urls))
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(sw_content)
    print_success(f"  ✓ sw.js 生成成功 (版本: {version})")


def generate_update_checker(version: str) -> str:
    """生成 PWA 自动更新检测脚本"""
    script = r'''
    <!-- PWA 自动更新检测 -->
    <script>
    const APP_VERSION = 'VERSION_PLACEHOLDER';
    console.log('[PWA] App version:', APP_VERSION);
    
    let registration = null;
    let updateFound = false;
    
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("./sw.js")
            .then(reg => {
                console.log('[PWA] ServiceWorker registration successful');
                registration = reg;
                
                reg.addEventListener('updatefound', () => {
                    console.log('[PWA] New update found!');
                    updateFound = true;
                    const newWorker = reg.installing;
                    
                    newWorker.addEventListener('statechange', () => {
                        console.log('[PWA] ServiceWorker state:', newWorker.state);
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            showUpdateNotification();
                        }
                    });
                });
                
                setInterval(() => {
                    console.log('[PWA] Checking for updates...');
                    reg.update().catch(err => {
                        console.log('[PWA] Update check failed:', err);
                    });
                }, 60 * 60 * 1000);
                
                setTimeout(() => {
                    reg.update().catch(err => {
                        console.log('[PWA] Initial update check failed:', err);
                    });
                }, 2000);
            })
            .catch(err => {
                console.log('[PWA] ServiceWorker registration failed:', err);
            });
        
        navigator.serviceWorker.addEventListener('controllerchange', () => {
            console.log('[PWA] Controller changed, reloading...');
            if (updateFound) {
                window.location.reload();
            }
        });
    }
    
    function showUpdateNotification() {
        const notification = document.createElement('div');
        notification.style.cssText = 'position:fixed;bottom:20px;right:20px;background:linear-gradient(135deg,#3b82f6 0%,#1d4ed8 100%);color:white;padding:16px 24px;border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,0.3);z-index:9999;animation:slideUp 0.3s ease-out;max-width:320px;';
        
        const inner = '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="10 6 16 12 10 18"></polyline></svg><strong>发现新版本！</strong></div><div style="display:flex;gap:8px;"><button id="updateNow" style="background:white;color:#1d4ed8;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:bold;flex:1;">立即更新</button><button id="laterBtn" style="background:rgba(255,255,255,0.2);color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;">稍后</button></div>';
        notification.innerHTML = inner;
        
        const style = document.createElement('style');
        style.textContent = '@keyframes slideUp{from{transform:translateY(100px);opacity:0}to{transform:translateY(0);opacity:1}}@keyframes slideDown{from{transform:translateY(0);opacity:1}to{transform:translateY(100px);opacity:0}}';
        document.head.appendChild(style);
        
        document.body.appendChild(notification);
        
        document.getElementById('updateNow').addEventListener('click', () => {
            if (registration && registration.waiting) {
                registration.waiting.postMessage({ type: 'SKIP_WAITING' });
            }
            notification.style.animation = 'slideDown 0.3s ease-in forwards';
            setTimeout(() => notification.remove(), 300);
        });
        
        document.getElementById('laterBtn').addEventListener('click', () => {
            notification.style.animation = 'slideDown 0.3s ease-in forwards';
            setTimeout(() => notification.remove(), 300);
        });
    }
    </script>
'''
    return script.replace('VERSION_PLACEHOLDER', version)


def calculate_build_version(resource_map: dict) -> str:
    """基于资源 hash 计算构建版本号"""
    combined_hashes = sorted(resource_map.values())
    hash_input = "|".join(combined_hashes)
    hash_obj = hashlib.sha256()
    hash_obj.update(hash_input.encode('utf-8'))
    return hash_obj.hexdigest()[:8]


def inject_vue_app_expose(app_js_path: str) -> None:
    """在 app.js 中注入 Vue app 实例暴露代码"""
    with open(app_js_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_pattern = "}).mount('#app');"
    
    if original_pattern in content:
        modified_content = content.replace(
            original_pattern, 
            "}); window.__VUE_APP__ = app.mount('#app');"
        )
        if "createApp({" in modified_content:
            modified_content = modified_content.replace(
                "createApp({", 
                "var app = createApp({"
            )
        else:
            print_warning("  ⚠ 未找到 createApp({，跳过 var app 注入，使用降级模式")
        with open(app_js_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        print_success("  ✓ Vue app 实例暴露代码注入成功")
    else:
        print_warning("  ⚠ 未找到 mount('#app') 调用，尝试追加注入代码")
        inject_code = '''

// === 自动注入代码 (由 build.py 添加) ===
(function() {
    function exposeVueApp() {
        var appElement = document.querySelector('#app');
        if (!appElement) return false;
        
        var vueApp = appElement.__vue_app__;
        if (vueApp) {
            if (vueApp._instance && vueApp._instance.proxy) {
                window.__VUE_APP__ = vueApp._instance.proxy;
                console.log('[RP-Hub] Vue app 已暴露');
                return true;
            }
            var container = vueApp._container;
            if (container && container.__vueParentComponent) {
                window.__VUE_APP__ = container.__vueParentComponent.proxy;
                console.log('[RP-Hub] Vue app 已暴露 (通过 container)');
                return true;
            }
        }
        if (appElement.__vueParentComponent) {
            window.__VUE_APP__ = appElement.__vueParentComponent.proxy;
            console.log('[RP-Hub] Vue app 已暴露 (通过 __vueParentComponent)');
            return true;
        }
        return false;
    }
    
    if (!exposeVueApp()) {
        for (var i = 1; i <= 10; i++) {
            (function(delay) {
                setTimeout(function() {
                    if (!window.__VUE_APP__) {
                        exposeVueApp();
                    }
                }, delay * 100);
            })(i);
        }
    }
})();
// === 注入代码结束 ===
'''
        with open(app_js_path, 'a', encoding='utf-8') as f:
            f.write(inject_code)
        print_success("  ✓ Vue app 实例暴露代码注入成功 (追加模式)")
    
    message_listener_code = '''

// === 消息监听注入代码 (由 build.py 添加) ===
window.addEventListener('message', function(e) {
    console.log('[RP-Hub] 收到消息：', e);
    if (e.data && e.data.data && e.data.data.file && window.__VUE_APP__) {
        var mockEvent = {
            target: {
                files: [e.data.data.file],
                value: e.data.data.url || ''
            }
        };
        window.__VUE_APP__.importCharacter(mockEvent);
    }
});
// === 消息监听代码结束 ===
'''
    with open(app_js_path, 'a', encoding='utf-8') as f:
        f.write(message_listener_code)
    print_success("  ✓ 消息监听代码注入成功")


def main():
    """主函数"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔════════════════════════════════════════════════════════════╗{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}║          RP-Hub 构建脚本 (Hash 缓存版本)                     ║{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚════════════════════════════════════════════════════════════╝{Colors.ENDC}\n")
    
    script_dir = Path(__file__).parent.absolute()
    build_dir = script_dir / "build"
    libs_dir = build_dir / "assets" / "libs"
    
    if build_dir.exists():
        print_warning("清理旧的 build 目录...")
        shutil.rmtree(build_dir)
    
    print_info("创建构建目录...")
    build_dir.mkdir(exist_ok=True)
    libs_dir.mkdir(parents=True, exist_ok=True)
    
    print_info("复制项目文件...")
    shutil.copy2(script_dir / "index.html", build_dir / "index.html")
    shutil.copytree(script_dir / "character", build_dir / "character", dirs_exist_ok=True)
    shutil.copytree(script_dir / "assets", build_dir / "assets", dirs_exist_ok=True)
    shutil.copy2(script_dir / "card-script.user.js", build_dir / "card-script.user.js")
    print_success("  ✓ 项目文件复制完成")
    
    print_info("替换域名...")
    replace_domain_in_files(build_dir, "rphforum.zeabur.app", "rphforum.smanx.xx.kg")
    print_success("  ✓ 域名替换完成")


    print_info("注入 Vue app 实例暴露代码...")
    app_js_path = build_dir / "assets" / "js" / "app.js"
    inject_vue_app_expose(str(app_js_path))
    
    print_info("移除导入后自动跳转到对话页面的逻辑...")
    replace_in_file(str(app_js_path), {
        '                    // Auto-select the new character and enter chat immediately.\n                    const newCharacterIndex = characters.value.length - 1;\n                    showAddCharacterMenu.value = false;\n                    await selectCharacter(newCharacterIndex, true);':
        '                    // Auto-select the new character without entering chat.\n                    const newCharacterIndex = characters.value.length - 1;\n                    showAddCharacterMenu.value = false;\n                    currentCharacterIndex.value = newCharacterIndex;\n                    saveData();\n                    showToast(\'角色卡导入完成\', \'success\');'
    })
    print_success("  ✓ 导入跳转逻辑已移除")
    
    print_info("清理历史消息残留的 UI 模板，仅最后一轮渲染...")
    replace_in_file(str(app_js_path), {
        '            if (!targetMessage) return false;\n            const top = activeUiTemplates.value\n                .filter(template => template.placement === \'top\' && !excludeTemplateIds.has(template.id))\n                .map(renderUiTemplateHtml)\n                .filter(Boolean);\n            const bottom = activeUiTemplates.value\n                .filter(template => template.placement === \'bottom\' && !excludeTemplateIds.has(template.id))\n                .map(renderUiTemplateHtml)\n                .filter(Boolean);\n            targetMessage.uiTemplateBlocks = {':
        '            if (!targetMessage) return false;\n            var _keepCount = 3;\n            var _assistantMsgs = chatHistory.value.filter(function(m) { return m && m.role === \'assistant\'; });\n            var _keepSet = new Set(_assistantMsgs.slice(-_keepCount));\n            chatHistory.value.forEach(function(msg) {\n                if (msg && msg.role === \'assistant\' && !_keepSet.has(msg)) {\n                    delete msg.uiTemplateBlocks;\n                }\n            });\n            const top = activeUiTemplates.value\n                .filter(template => template.placement === \'top\' && !excludeTemplateIds.has(template.id))\n                .map(renderUiTemplateHtml)\n                .filter(Boolean);\n            const bottom = activeUiTemplates.value\n                .filter(template => template.placement === \'bottom\' && !excludeTemplateIds.has(template.id))\n                .map(renderUiTemplateHtml)\n                .filter(Boolean);\n            targetMessage.uiTemplateBlocks = {'
    })
    print_success("  ✓ UI 模板清理逻辑已注入")
    
    files_to_download = [
        (
            [
                "https://cdn.tailwindcss.com/3.4.1",
                "https://cdn.tailwindcss.com",
            ], 
            libs_dir / "tailwindcss.js", 
            "tailwindcss.js",
            "TailwindCSS"
        ),
        (
            [
                "https://cdn.jsdelivr.net/npm/vue@3.4.21/dist/vue.global.prod.js",
                "https://unpkg.com/vue@3.4.21/dist/vue.global.prod.js",
            ], 
            libs_dir / "vue.global.prod.js", 
            "vue.global.prod.js",
            "Vue.js"
        ),
        (
            [
                "https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js",
                "https://unpkg.com/marked@12.0.0/marked.min.js",
            ], 
            libs_dir / "marked.min.js", 
            "marked.min.js",
            "Marked.js"
        ),
        (
            [
                "https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js",
                "https://unpkg.com/dompurify@3.0.6/dist/purify.min.js",
            ], 
            libs_dir / "purify.min.js", 
            "purify.min.js",
            "DOMPurify"
        ),
        (
            [
                "https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js",
                "https://unpkg.com/sortablejs@1.15.2/Sortable.min.js",
            ], 
            libs_dir / "Sortable.min.js", 
            "Sortable.min.js",
            "Sortable.js"
        ),
        (
            [
                "https://cdn.jsdelivr.net/npm/daisyui@4.7.2/dist/full.min.css",
                "https://unpkg.com/daisyui@4.7.2/dist/full.min.css",
            ], 
            libs_dir / "daisyui.min.css", 
            "daisyui.min.css",
            "DaisyUI"
        ),
        (
            [
                "https://cdn.jsdelivr.net/npm/localforage@1.10.0/dist/localforage.min.js",
                "https://unpkg.com/localforage@1.10.0/dist/localforage.min.js",
            ], 
            libs_dir / "localforage.min.js", 
            "localforage.min.js",
            "LocalForage"
        ),
        (
            [
                "https://api.dicebear.com/7.x/shapes/svg?seed=rp-hub&backgroundColor=1f2937",
            ], 
            build_dir / "assets" / "icon.svg", 
            "icon.svg",
            "PWA 图标"
        ),
    ]
    
    print_info("\n下载远程资源...")
    all_success = True
    resource_map = {}
    
    for urls, dest_path, filename, name in files_to_download:
        file_hash = download_file(urls, str(dest_path), name)
        if file_hash:
            hashed_path, file_hash = get_hashed_filename(str(dest_path))
            shutil.move(str(dest_path), hashed_path)
            resource_map[filename] = Path(hashed_path).name
            print_success(f"    ✓ 已重命名为 {Path(hashed_path).name}")
        else:
            all_success = False
    
    if not all_success:
        print_warning("\n部分文件下载失败，继续构建...\n")
    else:
        print_success("\n所有资源下载成功！\n")
    
    print_info("处理本地资源文件...")
    local_files = [
        (build_dir / "assets" / "css" / "styles.css", "styles.css"),
        (build_dir / "assets" / "js" / "app.js", "app.js"),
        (build_dir / "assets" / "js" / "utils.js", "utils.js"),
        (build_dir / "assets" / "js" / "card-utils.js", "card-utils.js"),
        (build_dir / "assets" / "js" / "ui-select.js", "ui-select.js"),
    ]
    
    for file_path, filename in local_files:
        if file_path.exists():
            hashed_path, file_hash = get_hashed_filename(str(file_path))
            shutil.move(str(file_path), hashed_path)
            resource_map[filename] = Path(hashed_path).name
            print_success(f"  ✓ {filename} -> {resource_map[filename]} (hash: {file_hash})")
    
    print_info("计算 index.html hash...")
    index_html_path = build_dir / "index.html"
    index_hash = calculate_file_hash(str(index_html_path))
    resource_map['index.html'] = f"index.{index_hash}.html"
    print_success(f"  ✓ index.html hash: {index_hash}")
    
    print_info("计算 character/index.html hash...")
    char_html_path = build_dir / "character" / "index.html"
    char_hash = calculate_file_hash(str(char_html_path))
    resource_map['character/index.html'] = f"index.{char_hash}.html"
    print_success(f"  ✓ character/index.html hash: {char_hash}")
    
    version = calculate_build_version(resource_map)
    print_info(f"\n构建版本号：{version} (基于资源内容计算)\n")
    
    print_info("处理 index.html...")
    shutil.copy2(index_html_path, index_html_path.with_suffix(".html.bak"))
    
    replacements = {
        "https://cdn.tailwindcss.com": f"./assets/libs/{resource_map['tailwindcss.js']}",
        "https://unpkg.com/vue@3/dist/vue.global.prod.js": f"./assets/libs/{resource_map['vue.global.prod.js']}",
        "https://cdn.jsdelivr.net/npm/marked/marked.min.js": f"./assets/libs/{resource_map['marked.min.js']}",
        "https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js": f"./assets/libs/{resource_map['purify.min.js']}",
        "https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js": f"./assets/libs/{resource_map['Sortable.min.js']}",
        "assets/js/app.js": f"./assets/js/{resource_map['app.js']}",
        "assets/js/utils.js": f"./assets/js/{resource_map['utils.js']}",
        "assets/js/card-utils.js": f"./assets/js/{resource_map['card-utils.js']}",
        "assets/js/ui-select.js": f"./assets/js/{resource_map['ui-select.js']}",
        "assets/css/styles.css": f"./assets/css/{resource_map['styles.css']}",
    }
    replace_in_file(str(index_html_path), replacements)
    
    with open(index_html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pwa_tags = f'<link rel="manifest" href="./manifest.json"><meta name="theme-color" content="#1f2937"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"><link rel="apple-touch-icon" href="./assets/{resource_map["icon.svg"]}">'
    if "</title>" in content:
        content = content.replace("</title>", f"</title>{pwa_tags}")
    else:
        print_warning("  ⚠ 未找到 </title>，跳过 PWA 标签注入")
    
    sw_register = generate_update_checker(version)
    if "</body>" in content:
        content = content.replace("</body>", sw_register + "</body>")
    else:
        print_warning("  ⚠ 未找到 </body>，跳过更新检测脚本注入")
    
    with open(index_html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print_success("  ✓ index.html 处理完成")
    
    print_info("处理 character/index.html...")
    char_html_path = build_dir / "character" / "index.html"
    shutil.copy2(char_html_path, char_html_path.with_suffix(".html.bak"))
    
    char_replacements = {
        "https://cdn.tailwindcss.com": f"../assets/libs/{resource_map['tailwindcss.js']}",
        "https://cdn.jsdelivr.net/npm/daisyui@4.7.2/dist/full.min.css": f"../assets/libs/{resource_map['daisyui.min.css']}",
        "https://unpkg.com/vue@3/dist/vue.global.prod.js": f"../assets/libs/{resource_map['vue.global.prod.js']}",
        "https://cdn.jsdelivr.net/npm/localforage@1.10.0/dist/localforage.min.js": f"../assets/libs/{resource_map['localforage.min.js']}",
        "../assets/js/card-utils.js": f"../assets/js/{resource_map['card-utils.js']}",
        "../assets/js/ui-select.js": f"../assets/js/{resource_map['ui-select.js']}",
    }
    replace_in_file(str(char_html_path), char_replacements)
    print_success("  ✓ character/index.html 处理完成")
    
    cache_urls = [
        f"./?v={version}",
        f"./index.html?v={version}",
        f"./character/index.html?v={version}",
        f"./assets/css/{resource_map['styles.css']}",
        f"./assets/js/{resource_map['app.js']}",
        f"./assets/js/{resource_map['utils.js']}",
        f"./assets/js/{resource_map['card-utils.js']}",
        f"./assets/js/{resource_map['ui-select.js']}",
        f"./assets/libs/{resource_map['tailwindcss.js']}",
        f"./assets/libs/{resource_map['vue.global.prod.js']}",
        f"./assets/libs/{resource_map['marked.min.js']}",
        f"./assets/libs/{resource_map['purify.min.js']}",
        f"./assets/libs/{resource_map['Sortable.min.js']}",
        f"./assets/libs/{resource_map['daisyui.min.css']}",
        f"./assets/libs/{resource_map['localforage.min.js']}",
        f"./assets/{resource_map['icon.svg']}",
        "./manifest.json",
    ]
    
    print_info("\n生成 PWA 支持文件...")
    generate_manifest_json(str(build_dir / "manifest.json"), f"./assets/{resource_map['icon.svg']}")
    generate_sw_js(str(build_dir / "sw.js"), version, cache_urls)
    
    print_info("\n" + "="*60)
    print_success("构建完成！")
    print_info("="*60 + "\n")
    
    print(f"{Colors.BOLD}构建目录：{Colors.ENDC}{build_dir}\n")
    print(f"{Colors.BOLD}版本号：{Colors.ENDC}{version} (基于资源内容计算)\n")
    print(f"{Colors.BOLD}Hash 资源映射：{Colors.ENDC}")
    for orig, hashed in sorted(resource_map.items()):
        print(f"  {orig:20s} -> {hashed}")
    
    print("\n" + "="*60)
    print(f"{Colors.BOLD}{Colors.YELLOW}PWA 功能：{Colors.ENDC}")
    print("="*60)
    print("✓ 基于内容的 Hash: 文件名包含内容 hash，内容不变则 hash 不变")
    print("✓ 智能版本管理: 版本号基于资源内容，只有内容变化才更新")
    print("✓ 高效的缓存策略: 只缓存我们项目构建的静态文件")
    print("✓ API 不缓存: 所有接口调用和外部请求直接从网络获取")
    print("✓ 避免无效更新: 资源不变时，即使重新构建也不会触发更新")
    print("✓ 增量更新: 只从旧缓存复制未变化的资源，避免全量重下载")
    print("✓ 实时更新通知: 发现新版本时显示漂亮的更新提示")
    print("✓ 一键更新: 用户点击即可立即更新")
    print("✓ 定期检查: 每小时自动检查更新")
    print("✓ 智能缓存: 优先使用缓存，后台更新资源")
    
    print("\n" + "="*60)
    print(f"{Colors.BOLD}{Colors.YELLOW}测试说明：{Colors.ENDC}")
    print("="*60)
    print("1. 进入 build 目录")
    print("2. 使用 HTTP 服务器启动（不能用 file:// 协议）")
    print(f"   - Python: cd {build_dir} && python3 -m http.server 8000")
    print("   - Node.js: npx http-server -p 8000")
    print("3. 在浏览器中访问 http://localhost:8000")
    print("4. 重新运行 build.py 生成新版本，浏览器会收到更新提示\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
