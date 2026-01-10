// 缓存名称和版本
const CACHE_NAME = 'yytoolssite-cache-v1';

// 需要缓存的资源列表
const ASSETS_TO_CACHE = [
  '/',
  '/static/navbar.css',
  '/static/hero.css',
  '/static/unified.css',
  '/static/style.css',
  '/static/scripts/main.js',
  '/static/manifest.json',
  'https://code.jquery.com/jquery-3.6.0.min.js'
];

// 安装事件 - 缓存资源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Opened cache');
        return cache.addAll(ASSETS_TO_CACHE);
      })
  );
  // 跳过等待，立即激活新的service worker
  self.skipWaiting();
});

// 激活事件 - 清理旧缓存
self.addEventListener('activate', (event) => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            // 删除旧缓存
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  // 立即获取控制权
  event.waitUntil(self.clients.claim());
});

// 网络请求事件 - 缓存优先策略
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // 如果缓存中存在资源，直接返回缓存
        if (response) {
          return response;
        }
        
        // 否则从网络获取
        return fetch(event.request)
          .then((response) => {
            // 检查响应是否有效
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }
            
            // 克隆响应，一份返回给浏览器，一份存入缓存
            const responseToCache = response.clone();
            
            caches.open(CACHE_NAME)
              .then((cache) => {
                cache.put(event.request, responseToCache);
              });
            
            return response;
          });
      })
  );
});

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
