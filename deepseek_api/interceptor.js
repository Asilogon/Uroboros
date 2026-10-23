/**
 * DeepSeek Network Interceptor
 * Injected into the browser to capture all fetch & XHR requests,
 * headers, authorization tokens, payloads, files, and responses.
 */
(function () {
    if (window.__ds_interceptor_installed) return;
    window.__ds_interceptor_installed = true;

    window.__ds_logs = window.__ds_logs || [];
    window.__ds_auth_captured = window.__ds_auth_captured || {};

    function sanitizeHeaders(headers) {
        const obj = {};
        if (!headers) return obj;
        if (headers instanceof Headers) {
            headers.forEach((v, k) => { obj[k.toLowerCase()] = v; });
        } else if (Array.isArray(headers)) {
            headers.forEach(([k, v]) => { obj[k.toLowerCase()] = v; });
        } else if (typeof headers === 'object') {
            for (const [k, v] of Object.entries(headers)) {
                obj[k.toLowerCase()] = String(v);
            }
        }
        return obj;
    }

    function checkAuthHeaders(headers) {
        if (!headers) return;
        const auth = headers['authorization'] || headers['Authorization'];
        if (auth && auth.startsWith('Bearer ')) {
            window.__ds_auth_captured.token = auth.replace('Bearer ', '').trim();
            window.__ds_auth_captured.authorization = auth;
        }
        for (const [k, v] of Object.entries(headers)) {
            if (k.startsWith('x-client-') || k.startsWith('x-app-') || k === 'x-ds-pow-response') {
                window.__ds_auth_captured[k] = v;
            }
        }
    }

    function pushLog(entry) {
        entry.timestamp = new Date().toISOString();
        window.__ds_logs.push(entry);
        if (window.__ds_logs.length > 1000) {
            window.__ds_logs.shift();
        }
    }

    // 1. Intercept window.fetch
    const originalFetch = window.fetch;
    window.fetch = async function (input, init = {}) {
        const url = (typeof input === 'string') ? input : (input && input.url ? input.url : String(input));
        const method = (init.method || (input && input.method) || 'GET').toUpperCase();
        const headers = sanitizeHeaders(init.headers || (input && input.headers));

        checkAuthHeaders(headers);

        let serializedBody = null;
        let fileInfo = null;

        if (init.body) {
            if (typeof init.body === 'string') {
                try {
                    serializedBody = JSON.parse(init.body);
                } catch (e) {
                    serializedBody = init.body;
                }
            } else if (init.body instanceof FormData) {
                serializedBody = {};
                fileInfo = [];
                for (const [key, val] of init.body.entries()) {
                    if (val instanceof File || val instanceof Blob) {
                        const info = {
                            field: key,
                            name: val.name || 'blob',
                            size: val.size,
                            type: val.type,
                            lastModified: val.lastModified
                        };
                        fileInfo.push(info);
                        serializedBody[key] = info;
                    } else {
                        serializedBody[key] = val;
                    }
                }
            } else if (init.body instanceof URLSearchParams) {
                serializedBody = init.body.toString();
            }
        }

        const reqId = Math.random().toString(36).substring(2, 10);
        pushLog({
            id: reqId,
            type: 'fetch',
            kind: 'request',
            method: method,
            url: url,
            headers: headers,
            body: serializedBody,
            files: fileInfo
        });

        try {
            const response = await originalFetch.apply(this, arguments);
            const clone = response.clone();
            const resHeaders = sanitizeHeaders(clone.headers);
            const contentType = resHeaders['content-type'] || '';

            if (contentType.includes('text/event-stream')) {
                pushLog({
                    id: reqId,
                    type: 'fetch',
                    kind: 'response_stream',
                    method: method,
                    url: url,
                    status: clone.status,
                    statusText: clone.statusText,
                    headers: resHeaders
                });
            } else {
                clone.text().then(text => {
                    let body = text;
                    try { body = JSON.parse(text); } catch (e) {}

                    // Auto-detect user token from response body if present
                    if (body && typeof body === 'object') {
                        if (body.data && body.data.token) {
                            window.__ds_auth_captured.token = body.data.token;
                        }
                    }

                    pushLog({
                        id: reqId,
                        type: 'fetch',
                        kind: 'response',
                        method: method,
                        url: url,
                        status: clone.status,
                        statusText: clone.statusText,
                        headers: resHeaders,
                        body: body
                    });
                }).catch(() => {});
            }

            return response;
        } catch (err) {
            pushLog({
                id: reqId,
                type: 'fetch',
                kind: 'error',
                method: method,
                url: url,
                error: String(err)
            });
            throw err;
        }
    };

    // 2. Intercept XMLHttpRequest
    const origOpen = XMLHttpRequest.prototype.open;
    const origSend = XMLHttpRequest.prototype.send;
    const origSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;

    XMLHttpRequest.prototype.open = function (method, url, ...rest) {
        this.__ds_data = {
            id: Math.random().toString(36).substring(2, 10),
            type: 'xhr',
            method: (method || 'GET').toUpperCase(),
            url: String(url),
            headers: {}
        };
        return origOpen.apply(this, [method, url, ...rest]);
    };

    XMLHttpRequest.prototype.setRequestHeader = function (header, value) {
        if (this.__ds_data && this.__ds_data.headers) {
            this.__ds_data.headers[header.toLowerCase()] = value;
            checkAuthHeaders(this.__ds_data.headers);
        }
        return origSetRequestHeader.apply(this, arguments);
    };

    XMLHttpRequest.prototype.send = function (body) {
        if (this.__ds_data) {
            let serializedBody = body;
            let fileInfo = null;

            if (typeof body === 'string') {
                try { serializedBody = JSON.parse(body); } catch (e) {}
            } else if (body instanceof FormData) {
                serializedBody = {};
                fileInfo = [];
                for (const [key, val] of body.entries()) {
                    if (val instanceof File || val instanceof Blob) {
                        const info = {
                            field: key,
                            name: val.name || 'blob',
                            size: val.size,
                            type: val.type
                        };
                        fileInfo.push(info);
                        serializedBody[key] = info;
                    } else {
                        serializedBody[key] = val;
                    }
                }
            }

            pushLog({
                id: this.__ds_data.id,
                type: 'xhr',
                kind: 'request',
                method: this.__ds_data.method,
                url: this.__ds_data.url,
                headers: this.__ds_data.headers,
                body: serializedBody,
                files: fileInfo
            });

            this.addEventListener('load', () => {
                let resBody = this.responseText;
                try { resBody = JSON.parse(resBody); } catch (e) {}
                pushLog({
                    id: this.__ds_data.id,
                    type: 'xhr',
                    kind: 'response',
                    method: this.__ds_data.method,
                    url: this.__ds_data.url,
                    status: this.status,
                    statusText: this.statusText,
                    body: resBody
                });
            });
        }
        return origSend.apply(this, arguments);
    };

    console.log('[DeepSeek Interceptor] Initialized successfully.');
})();
