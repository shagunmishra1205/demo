const CACHE_NAME = "awaazform-v1";

const FILES_TO_CACHE = [
    "/",
    "/index.html",
    "/css/styles.css",
    "/js/app.js",
    "/js/api.js",
    "/js/data.js",
    "/js/i18n.js",
    "/js/speech.js"
];

self.addEventListener("install", event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache =>
            cache.addAll(FILES_TO_CACHE)
        )
    );
});

self.addEventListener("fetch", event => {
    const url = new URL(event.request.url);

    // Only cache same-origin GET requests.
    if (event.request.method !== "GET" || url.origin !== self.location.origin) {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then(response => {
                if (response.ok) {
                    const copy = response.clone();
                    caches.open(CACHE_NAME).then(cache =>
                        cache.put(event.request, copy)
                    );
                }
                return response;
            })
            .catch(() => caches.match(event.request))
    );
});

self.addEventListener("activate", event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            )
        )
    );
});