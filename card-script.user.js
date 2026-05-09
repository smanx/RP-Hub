// ==UserScript==
// @name         卡片图片获取工具
// @namespace    http://tampermonkey.net/
// @version      2.2
// @description  为页面卡片添加获取图片UUID的功能
// @author       You
// @match        file:///C:/mydata/codes/RP-Hub/test2.html
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // 创建主按钮（可拖动）
    function createMainButton() {
        const button = document.createElement('button');
        button.textContent = '📷';
        button.style.cssText = 'position: fixed; top: 74px; right: 20px; z-index: 9999; padding: 6px; width: 32px; height: 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 16px; cursor: move; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4); transition: all 0.3s ease; user-select: none; display: flex; align-items: center; justify-content: center;';
        
        // 拖动功能变量
        let isDragging = false;
        let currentX;
        let currentY;
        let initialX;
        let initialY;
        let xOffset = 0;
        let yOffset = 0;
        
        // 鼠标按下事件
        button.addEventListener('mousedown', function(e) {
            // 如果不是左键，不处理
            if (e.button !== 0) return;
            
            initialX = e.clientX - xOffset;
            initialY = e.clientY - yOffset;
            isDragging = true;
            this.style.cursor = 'grabbing';
            this.style.transition = 'none';
        });
        
        // 鼠标移动事件
        document.addEventListener('mousemove', function(e) {
            if (isDragging) {
                e.preventDefault();
                currentX = e.clientX - initialX;
                currentY = e.clientY - initialY;
                xOffset = currentX;
                yOffset = currentY;
                button.style.right = 'auto';
                button.style.left = currentX + 'px';
                button.style.top = currentY + 'px';
            }
        });
        
        // 鼠标释放事件
        document.addEventListener('mouseup', function() {
            if (isDragging) {
                isDragging = false;
                button.style.cursor = 'move';
                button.style.transition = 'all 0.3s ease';
            }
        });
        
        // 点击事件（区分拖动和点击）
        let clickStartTime = 0;
        button.addEventListener('mousedown', function() {
            clickStartTime = Date.now();
        });
        
        button.addEventListener('mouseup', function(e) {
            const clickDuration = Date.now() - clickStartTime;
            // 如果点击时间小于200ms，视为点击
            if (clickDuration < 200) {
                addCardButtons();
            }
        });
        
        button.addEventListener('mouseenter', function() {
            if (!isDragging) {
                this.style.transform = 'translateY(-2px)';
                this.style.boxShadow = '0 6px 20px rgba(102, 126, 234, 0.6)';
            }
        });
        
        button.addEventListener('mouseleave', function() {
            if (!isDragging) {
                this.style.transform = 'translateY(0)';
                this.style.boxShadow = '0 4px 15px rgba(102, 126, 234, 0.4)';
            }
        });
        
        document.body.appendChild(button);
    }

    // 为每个卡片添加按钮
    function addCardButtons() {
        const cards = document.querySelectorAll('.group.relative.flex.bg-white.rounded-3xl');
        
        // 添加旋转动画样式
        const style = document.createElement('style');
        style.textContent = '@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }';
        document.head.appendChild(style);
        
        cards.forEach(function(card, index) {
            // 检查是否已经添加过按钮
            if (card.querySelector('.card-img-button')) return;
            
            // 创建卡片按钮
            const cardButton = document.createElement('button');
            cardButton.textContent = '📋';
            cardButton.className = 'card-img-button';
            cardButton.style.cssText = 'position: absolute; top: 10px; right: 10px; z-index: 100; width: 36px; height: 36px; background: rgba(255, 255, 255, 0.95); border: 2px solid #667eea; border-radius: 50%; font-size: 18px; cursor: pointer; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15); transition: all 0.3s ease; display: flex; align-items: center; justify-content: center;';
            
            cardButton.addEventListener('mouseenter', function() {
                this.style.transform = 'scale(1.1)';
                this.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
            });
            
            cardButton.addEventListener('mouseleave', function() {
                this.style.transform = 'scale(1)';
                this.style.background = 'rgba(255, 255, 255, 0.95)';
            });
            
            cardButton.addEventListener('click', function(e) {
                e.stopPropagation();
                const img = card.querySelector('img');
                if (img && img.src) {
                    // 从URL中提取UUID
                    const uuidMatch = img.src.match(/\/api\/cards\/([a-f0-9-]{36})\//);
                    if (uuidMatch) {
                        const uuid = uuidMatch[1];
                        const timestamp = Date.now();
                        const url = 'https://rps.good.hidns.vip/characters/data/' + uuid + '.png?t=' + timestamp;
                        
                        // 开始下载，按钮显示加载效果
                        cardButton.textContent = '';
                        cardButton.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                        cardButton.style.animation = 'spin 1s linear infinite';
                        cardButton.innerHTML = '<svg style="width: 18px; height: 18px; fill: none; stroke: white; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round"><circle cx="9" cy="9" r="7" opacity="0.25"></circle><path d="M16 9a7 7 0 0 0-7-7" opacity="0.75"></path></svg>';
                        
                        // 下载图片为File对象
                        fetch(url)
                            .then(function(response) { return response.blob(); })
                            .then(function(blob) {
                                const file = new File([blob], uuid + '.png', { type: blob.type });
                                const message = { type: 'action', data: { uuid: uuid, url: url, file: file } };
                                console.log('postMessage参数:', message);
                                window.parent.postMessage(message, '*');
                                
                                // 下载成功，按钮显示绿色
                                cardButton.style.animation = 'none';
                                cardButton.innerHTML = '';
                                cardButton.textContent = '✓';
                                cardButton.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
                                cardButton.style.borderColor = '#10b981';
                                
                                // 2秒后恢复原状
                                setTimeout(function() {
                                    cardButton.textContent = '📋';
                                    cardButton.style.background = 'rgba(255, 255, 255, 0.95)';
                                    cardButton.style.borderColor = '#667eea';
                                }, 2000);
                            })
                            .catch(function(error) {
                                console.error('下载图片失败:', error);
                                const message = { type: 'error', data: { message: '下载图片失败' } };
                                console.log('error:', message);
                                
                                // 下载失败，按钮显示红色
                                cardButton.style.animation = 'none';
                                cardButton.innerHTML = '';
                                cardButton.textContent = '✗';
                                cardButton.style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
                                cardButton.style.borderColor = '#ef4444';
                                
                                // 2秒后恢复原状
                                setTimeout(function() {
                                    cardButton.textContent = '📋';
                                    cardButton.style.background = 'rgba(255, 255, 255, 0.95)';
                                    cardButton.style.borderColor = '#667eea';
                                }, 2000);
                            });
                    } else {
                        const message = { type: 'error', data: { message: '未找到UUID' } };
                        console.log('error:', message);
                    }
                } else {
                    alert('未找到图片');
                }
            });
            
            // 确保卡片是相对定位
            if (getComputedStyle(card).position !== 'relative') {
                card.style.position = 'relative';
            }
            
            card.appendChild(cardButton);
        });
        
        const message = { type: 'info', data: { message: '已为 ' + cards.length + ' 个卡片添加按钮！' } };
        console.log('message:', message);
    }

    // 等待页面加载完成后执行
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createMainButton);
    } else {
        createMainButton();
    }
    
    // 也可以在页面完全加载后再次尝试（处理动态加载的内容）
    window.addEventListener('load', function() {
        setTimeout(createMainButton, 1000);
    });
})();
