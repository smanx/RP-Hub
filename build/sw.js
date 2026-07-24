const CACHE_NAME = 'rp-hub-dbcc68c3';
const urlsToCache = ['./?v=dbcc68c3', './index.html?v=dbcc68c3', './character/index.html?v=dbcc68c3', './assets/css/styles.859da972.css', './assets/js/app.030b54e9.js', './assets/js/utils.5036d2be.js', './assets/js/card-utils.b5e0efa5.js', './assets/js/ui-select.7ef8ef39.js', './assets/libs/tailwindcss.f6f32385.js', './assets/libs/vue.global.prod.49631014.js', './assets/libs/marked.min.eb1f6b19.js', './assets/libs/purify.min.ea4b0908.js', './assets/libs/Sortable.min.ca684307.js', './assets/libs/daisyui.min.87075ae3.css', './assets/libs/localforage.min.cc168d95.js', './assets/icon.085bbc03.svg', './manifest.json', './assets/css/lora.cde21e8c.css', './assets/fonts/0QIhMX1D_JOuMw_LLPtLp_A.woff2', './assets/fonts/0QIhMX1D_JOuMw_LJftLp_A.woff2', './assets/fonts/0QIhMX1D_JOuMw_LXftLp_A.woff2', './assets/fonts/0QIhMX1D_JOuMw_LT_tLp_A.woff2', './assets/fonts/0QIhMX1D_JOuMw_LLvtLp_A.woff2', './assets/fonts/0QIhMX1D_JOuMw_LL_tLp_A.woff2', './assets/fonts/0QIhMX1D_JOuMw_LIftL.woff2', './assets/fonts/0QIvMX1D_JOuMwf7I-NP.woff2', './assets/fonts/0QIvMX1D_JOuMw77I-NP.woff2', './assets/fonts/0QIvMX1D_JOuM3b7I-NP.woff2', './assets/fonts/0QIvMX1D_JOuM2T7I-NP.woff2', './assets/fonts/0QIvMX1D_JOuMwX7I-NP.woff2', './assets/fonts/0QIvMX1D_JOuMwT7I-NP.woff2', './assets/fonts/0QIvMX1D_JOuMwr7Iw.woff2'];

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
    console.log('[ServiceWorker] Installing new version:', 'dbcc68c3');
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
    console.log('[ServiceWorker] Activating new version:', 'dbcc68c3');
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
});