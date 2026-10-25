// 지역가입자 건강보험료 계산기 오프라인 동작
// 화면(HTML)은 인터넷이 되면 항상 최신본을 받고, 끊겼을 때만 저장본을 쓴다(보험료율이 해마다 바뀌므로).
// 아이콘 등 나머지 파일은 저장본을 먼저 쓴다. 파일을 바꿔 배포할 때는 CACHE 이름의 날짜를 올린다.
const CACHE = 'jiyeok-hi-2026-10-25';
const ASSETS = [
    './',
    './index.html',
    './manifest.webmanifest',
    './icons/icon-192.png',
    './icons/icon-512.png',
    './icons/icon-maskable-512.png',
    './icons/apple-touch-icon.png',
    './icons/favicon-32.png'
];

self.addEventListener('install', (e) => {
    e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(keys.filter((k) => k.startsWith('jiyeok-hi-') && k !== CACHE).map((k) => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (e) => {
    const req = e.request;
    if (req.method !== 'GET') return;
    const url = new URL(req.url);
    if (url.origin !== self.location.origin) return;   // 글꼴 등 외부 파일은 브라우저에 맡긴다

    if (req.mode === 'navigate') {
        e.respondWith(
            fetch(req)
                .then((res) => {
                    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put('./index.html', copy)); }
                    return res;
                })
                .catch(() => caches.match('./index.html').then((r) => r || caches.match('./')))
        );
        return;
    }

    e.respondWith(
        caches.match(req, { ignoreSearch: true }).then((hit) => hit || fetch(req).then((res) => {
            if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
            return res;
        }))
    );
});
