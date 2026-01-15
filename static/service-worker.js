// 缓存名称和版本 - 优化版本管理
const CACHE_VERSION = 'v2';
const CACHE_NAME = `yytoolssite-cache-${CACHE_VERSION}`;
const STATIC_CACHE_NAME = `yytoolssite-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE_NAME = `yytoolssite-dynamic-${CACHE_VERSION}`;

// 需要缓存的核心静态资源列表
const CORE_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

// 需要缓存的静态资源列表（带版本号的资源会自动缓存）
const STATIC_RESOURCES = [
  '/static/navbar.css',
  '/static/hero.css',
  '/static/unified.css',
  '/static/style.css',
  '/static/account.css',
  '/static/ai.css',
  '/static/auth.css',
  '/static/blog.css',
  '/static/detail.css',
  '/static/file_detail.css',
  '/static/upload.css',
  '/static/user_center.css',
  '/static/scripts/main.js',
  '/static/scripts/folder_detail.js',
  '/static/scripts/project_folders.js',
  '/static/ai.js',
  '/static/upload.js',
  '/static/user_center.js',
  'https://code.jquery.com/jquery-3.6.0.min.js'
];

// 安装事件 - 预缓存核心资源
self.addEventListener('install', (event) => {
  event.waitUntil(
    Promise.all([
      // 预缓存核心静态资源
      caches.open(STATIC_CACHE_NAME)
        .then((cache) => {
          console.log('预缓存核心静态资源');
          return cache.addAll(CORE_ASSETS);
        }),
      // 预缓存其他静态资源
      caches.open(STATIC_CACHE_NAME)
        .then((cache) => {
          console.log('预缓存其他静态资源');
          return cache.addAll(STATIC_RESOURCES);
        })
    ])
  );
  // 跳过等待，立即激活新的service worker
  self.skipWaiting();
});

// 激活事件 - 清理旧缓存并更新缓存
self.addEventListener('activate', (event) => {
  const cacheWhitelist = [STATIC_CACHE_NAME, DYNAMIC_CACHE_NAME];
  
  event.waitUntil(
    Promise.all([
      // 清理旧缓存
      caches.keys().then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheWhitelist.indexOf(cacheName) === -1) {
              console.log('删除旧缓存:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      }),
      // 立即获取控制权
      self.clients.claim()
    ])
  );
});

// 网络请求事件 - 优化的缓存策略
self.addEventListener('fetch', (event) => {
  const request = event.request;
  
  // 忽略非GET请求
  if (request.method !== 'GET') {
    return;
  }
  
  // 对于HTML请求，使用网络优先策略，同时更新缓存
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          
          // 克隆响应，一份返回给浏览器，一份存入缓存
          const responseToCache = response.clone();
          
          // 存入动态缓存
          caches.open(DYNAMIC_CACHE_NAME)
            .then((cache) => {
              cache.put(request, responseToCache);
            });
          
          return response;
        })
        .catch(() => {
          // 如果网络请求失败，返回缓存中的页面
          return caches.match(request)
            .then((cachedResponse) => {
              // 如果缓存中有对应页面，返回缓存
              if (cachedResponse) {
                return cachedResponse;
              }
              // 否则返回首页缓存
              return caches.match('/');
            });
        })
    );
  } 
  // 对于静态资源（CSS, JS, 图片等），使用缓存优先策略
  else {
    event.respondWith(
      caches.match(request)
        .then((cachedResponse) => {
          // 如果缓存中存在资源，直接返回缓存
          if (cachedResponse) {
            // 后台更新缓存，确保资源是最新的
            updateCache(request);
            return cachedResponse;
          }
          
          // 否则从网络获取
          return fetch(request)
            .then((response) => {
              // 检查响应是否有效
              if (!response || response.status !== 200 || response.type !== 'basic') {
                return response;
              }
              
              // 克隆响应，一份返回给浏览器，一份存入缓存
              const responseToCache = response.clone();
              
              // 存入静态缓存
              caches.open(STATIC_CACHE_NAME)
                .then((cache) => {
                  cache.put(request, responseToCache);
                });
              
              return response;
            })
            .catch(() => {
              // 如果是图片请求，返回默认图片占位符
              if (request.headers.get('accept')?.includes('image')) {
                return new Response(
                  '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><rect width="100" height="100" fill="#f8fafc"/><text x="50" y="50" font-size="12" text-anchor="middle" dy=".3em" fill="#64748b">图片加载失败</text></svg>',
                  { headers: { 'Content-Type': 'image/svg+xml' } }
                );
              }
              return null;
            });
        })
    );
  }
});

// 后台更新缓存函数
async function updateCache(request) {
  try {
    const response = await fetch(request);
    if (response.status === 200 && response.type === 'basic') {
      const responseToCache = response.clone();
      const cache = await caches.open(STATIC_CACHE_NAME);
      await cache.put(request, responseToCache);
    }
  } catch (error) {
    // 忽略网络错误
    console.log('后台更新缓存失败:', error);
  }
}

// 定期清理动态缓存，只保留最近访问的资源
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CLEANUP_DYNAMIC_CACHE') {
    cleanupDynamicCache();
  }
});

// 清理动态缓存函数
async function cleanupDynamicCache() {
  const cache = await caches.open(DYNAMIC_CACHE_NAME);
  const requests = await cache.keys();
  
  // 只保留最近访问的20个资源
  if (requests.length > 20) {
    const requestsToDelete = requests.slice(0, requests.length - 20);
    await Promise.all(
      requestsToDelete.map(request => cache.delete(request))
    );
    console.log('已清理动态缓存，保留最近20个资源');
  }
}

// 后台同步事件 - 用于离线时的数据同步
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-data') {
    event.waitUntil(syncData());
  }
});

// 数据同步函数
async function syncData() {
  console.log('Syncing data...');
  // 这里可以添加离线数据同步逻辑
  // 例如：发送离线表单数据、上传离线文件等
}

// 推送通知事件 - 用于接收推送通知
self.addEventListener('push', (event) => {
  if (event.data) {
    const data = event.data.json();
    const options = {
      body: data.body,
      icon: '/static/icons/icon-192x192.png',
      badge: '/static/icons/icon-72x72.png',
      vibrate: [100, 50, 100],
      data: {
        url: data.url || '/'
      }
    };
    
    event.waitUntil(
      self.registration.showNotification(data.title, options)
    );
  }
});

// 通知点击事件 - 点击通知后打开对应页面
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // 如果已有打开的窗口，聚焦到该窗口
      for (const client of clientList) {
        if (client.url === event.notification.data.url && 'focus' in client) {
          return client.focus();
        }
      }
      // 否则打开新窗口
      if (clients.openWindow) {
        return clients.openWindow(event.notification.data.url);
      }
    })
  );
});

// 周期性后台同步事件 - 用于定期更新缓存
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'update-cache') {
    event.waitUntil(updateStaticCache());
  }
});

// 更新静态缓存函数
async function updateStaticCache() {
  console.log('定期更新静态缓存');
  try {
    const cache = await caches.open(STATIC_CACHE_NAME);
    await cache.addAll(STATIC_RESOURCES);
    console.log('静态缓存更新完成');
  } catch (error) {
    console.error('静态缓存更新失败:', error);
  }
}
