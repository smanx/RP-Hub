#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RP-Hub 构建脚本
用于下载远程资源到本地并添加 PWA 支持
可以在本地运行或被 GitHub Actions 调用
"""

import os
import sys
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


def download_file(urls: list, dest_path: str, name: str) -> bool:
    """下载文件到指定路径，支持多个备用源"""
    if isinstance(urls, str):
        urls = [urls]
    
    print(f"  - 正在下载 {name}...")
    for i, url in enumerate(urls):
        try:
            # 添加 User-Agent 避免被一些 CDN 阻止
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response, open(dest_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            
            if os.path.exists(dest_path):
                size = os.path.getsize(dest_path)
                print_success(f"    ✓ {name} 下载成功 ({size / 1024:.1f} KB)")
                return True
        except Exception as e:
            if i < len(urls) - 1:
                print_warning(f"    备用源 {i+1} 失败，尝试下一个...")
            else:
                print_error(f"    ✗ {name} 下载失败: {e}")
    return False


def replace_in_file(file_path: str, replacements: dict) -> None:
    """替换文件中的内容"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old_str, new_str in replacements.items():
        content = content.replace(old_str, new_str)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def generate_manifest_json(output_path: str) -> None:
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
      "src": "assets/icon.svg",
      "sizes": "any",
      "type": "image/svg+xml",
      "purpose": "any maskable"
    }
  ]
}'''
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(manifest_content)
    print_success("  ✓ manifest.json 生成成功")


def generate_sw_js(output_path: str) -> None:
    """生成 Service Worker 文件"""
    sw_content = '''const CACHE_NAME = 'rp-hub-v2';
const urlsToCache = [
  './',
  './index.html',
  './character/index.html',
  './assets/css/styles.css',
  './assets/js/app.js',
  './assets/js/utils.js',
  './assets/libs/tailwindcss.js',
  './assets/libs/vue.global.prod.js',
  './assets/libs/marked.min.js',
  './assets/libs/purify.min.js',
  './assets/libs/Sortable.min.js',
  './assets/libs/daisyui.min.css',
  './assets/libs/localforage.min.js',
  './assets/icon.svg',
  './manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache.map(url => new Request(url, { cache: 'no-cache' })));
      })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

self.addEventListener('fetch', (event) => {
  const requestUrl = new URL(event.request.url);
  
  // 只处理 http/https 请求
  if (!requestUrl.protocol.startsWith('http')) {
    return;
  }
  
  event.respondWith(
    caches.match(event.request, { ignoreSearch: true })
      .then((response) => {
        // 如果缓存中有，直接返回
        if (response) {
          return response;
        }
        // 否则从网络获取
        return fetch(event.request).then((response) => {
          if (!response || response.status !== 200) {
            return response;
          }
          // 克隆响应
          let responseToCache = response.clone();
          caches.open(CACHE_NAME)
            .then((cache) => {
              cache.put(event.request, responseToCache);
            });
          return response;
        }).catch(() => {
          return caches.match(event.request, { ignoreSearch: true });
        });
      })
  );
});'''
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(sw_content)
    print_success("  ✓ sw.js 生成成功")


def main():
    """主函数"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔════════════════════════════════════════════════════════════╗{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}║          RP-Hub 构建脚本                                    ║{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚════════════════════════════════════════════════════════════╝{Colors.ENDC}\n")
    
    # 设置路径
    script_dir = Path(__file__).parent.absolute()
    build_dir = script_dir / "build"
    libs_dir = build_dir / "assets" / "libs"
    
    # 清理旧的 build 目录
    if build_dir.exists():
        print_warning("清理旧的 build 目录...")
        shutil.rmtree(build_dir)
    
    # 创建目录结构
    print_info("创建构建目录...")
    build_dir.mkdir(exist_ok=True)
    libs_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制原始文件
    print_info("复制项目文件...")
    shutil.copy2(script_dir / "index.html", build_dir / "index.html")
    shutil.copytree(script_dir / "character", build_dir / "character", dirs_exist_ok=True)
    shutil.copytree(script_dir / "assets", build_dir / "assets", dirs_exist_ok=True)
    print_success("  ✓ 项目文件复制完成")
    
    # 定义要下载的文件，支持多个备用源
    files_to_download = [
        (
            [
                "https://cdn.tailwindcss.com/3.4.1",
                "https://cdn.tailwindcss.com",
            ], 
            libs_dir / "tailwindcss.js", "TailwindCSS"
        ),
        (
            [
                "https://unpkg.com/vue@3/dist/vue.global.prod.js",
                "https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js",
            ], 
            libs_dir / "vue.global.prod.js", "Vue.js"
        ),
        (
            [
                "https://cdn.jsdelivr.net/npm/marked/marked.min.js",
                "https://unpkg.com/marked/marked.min.js",
            ], 
            libs_dir / "marked.min.js", "Marked.js"
        ),
        (
            [
                "https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js",
                "https://unpkg.com/dompurify@3.0.6/dist/purify.min.js",
            ], 
            libs_dir / "purify.min.js", "DOMPurify"
        ),
        (
            [
                "https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js",
                "https://unpkg.com/sortablejs@latest/Sortable.min.js",
            ], 
            libs_dir / "Sortable.min.js", "Sortable.js"
        ),
        (
            [
                "https://cdn.jsdelivr.net/npm/daisyui@4.7.2/dist/full.min.css",
                "https://unpkg.com/daisyui@4.7.2/dist/full.min.css",
            ], 
            libs_dir / "daisyui.min.css", "DaisyUI"
        ),
        (
            [
                "https://cdn.jsdelivr.net/npm/localforage@1.10.0/dist/localforage.min.js",
                "https://unpkg.com/localforage@1.10.0/dist/localforage.min.js",
            ], 
            libs_dir / "localforage.min.js", "LocalForage"
        ),
        (
            [
                "https://api.dicebear.com/7.x/shapes/svg?seed=rp-hub&backgroundColor=1f2937",
            ], 
            build_dir / "assets" / "icon.svg", "PWA 图标"
        ),
    ]
    
    # 下载文件
    print_info("\n下载远程资源...")
    all_success = True
    for url, dest, name in files_to_download:
        if not download_file(url, str(dest), name):
            all_success = False
    
    if not all_success:
        print_error("\n部分文件下载失败，继续构建...\n")
    else:
        print_success("\n所有资源下载成功！\n")
    
    # 修改 index.html
    print_info("处理 index.html...")
    index_html_path = build_dir / "index.html"
    shutil.copy2(index_html_path, index_html_path.with_suffix(".html.bak"))
    
    # 替换 CDN 链接
    replacements = {
        "https://cdn.tailwindcss.com": "assets/libs/tailwindcss.js",
        "https://unpkg.com/vue@3/dist/vue.global.prod.js": "assets/libs/vue.global.prod.js",
        "https://cdn.jsdelivr.net/npm/marked/marked.min.js": "assets/libs/marked.min.js",
        "https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js": "assets/libs/purify.min.js",
        "https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js": "assets/libs/Sortable.min.js",
    }
    replace_in_file(str(index_html_path), replacements)
    
    # 添加 PWA 标签
    with open(index_html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pwa_tags = '<link rel="manifest" href="./manifest.json"><meta name="theme-color" content="#1f2937"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"><link rel="apple-touch-icon" href="./assets/icon.svg">'
    content = content.replace("</title>", f"</title>{pwa_tags}")
    
    sw_register = '''    <script>if("serviceWorker" in navigator){navigator.serviceWorker.register("./sw.js").then(function(registration){console.log("ServiceWorker registration successful");}).catch(function(err){console.log("ServiceWorker registration failed: ", err);});}</script></body>'''
    content = content.replace("</body>", sw_register)
    
    with open(index_html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print_success("  ✓ index.html 处理完成")
    
    # 修改 character/index.html
    print_info("处理 character/index.html...")
    char_html_path = build_dir / "character" / "index.html"
    shutil.copy2(char_html_path, char_html_path.with_suffix(".html.bak"))
    
    char_replacements = {
        "https://cdn.tailwindcss.com": "../assets/libs/tailwindcss.js",
        "https://cdn.jsdelivr.net/npm/daisyui@4.7.2/dist/full.min.css": "../assets/libs/daisyui.min.css",
        "https://unpkg.com/vue@3/dist/vue.global.prod.js": "../assets/libs/vue.global.prod.js",
        "https://cdn.jsdelivr.net/npm/localforage@1.10.0/dist/localforage.min.js": "../assets/libs/localforage.min.js",
    }
    replace_in_file(str(char_html_path), char_replacements)
    print_success("  ✓ character/index.html 处理完成")
    
    # 生成 PWA 文件
    print_info("生成 PWA 支持文件...")
    generate_manifest_json(str(build_dir / "manifest.json"))
    generate_sw_js(str(build_dir / "sw.js"))
    
    # 显示构建结果
    print_info("\n" + "="*60)
    print_success("构建完成！")
    print_info("="*60 + "\n")
    
    print(f"{Colors.BOLD}构建目录：{Colors.ENDC}{build_dir}\n")
    print(f"{Colors.BOLD}已下载的库文件：{Colors.ENDC}")
    for f in libs_dir.iterdir():
        size = os.path.getsize(f) / 1024
        print(f"  - {f.name} ({size:.1f} KB)")
    
    print("\n" + "="*60)
    print(f"{Colors.BOLD}{Colors.YELLOW}测试说明：{Colors.ENDC}")
    print("="*60)
    print("1. 进入 build 目录")
    print("2. 使用 HTTP 服务器启动（不能用 file:// 协议）")
    print(f"   - Python: cd {build_dir} && python3 -m http.server 8000")
    print("   - Node.js: npx http-server -p 8000")
    print("3. 在浏览器中访问 http://localhost:8000")
    print("4. 测试 PWA 功能：浏览器地址栏应该有安装按钮\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
