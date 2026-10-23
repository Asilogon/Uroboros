/**
 * DeepSeek Network Interceptor (Stealth & Native Code Protected)
 * Only logs application API requests. Ignores all captcha and verification endpoints.
 * Protects Function.prototype.toString to return '[native code]' for all wrapped methods.
 */
(function () {
    if (window.__ds_interceptor_installed) return;
    window.__ds_interceptor_installed = true;

    window.__ds_logs = window.__ds_logs || [];
    window.__ds_auth_captured = window.__ds_auth_captured || {};

    // 1. Native toString protection
    const nativeToString = Function.prototype.toString;
    const protectedFunctions = new WeakSet();

    function markNative(fn) {
        protectedFunctions.add(fn);
        return fn;
    }

    Function.prototype.toString = function toString() {
        if (protectedFunctions.has(this)) {
            const name = this.name || '';
            return 'function ' + name + '() { [native code] }';
        }
        return nativeToString.apply(this, arguments);
    };
    markNative(Function.prototype.toString);

    // Filter out captcha and telemetry domains
    function isCaptchaOrTelemetry(url) {
        if (!url) return false;
        const lower = String(url).toLowerCase();
        return (
            lower.includes('volces.com') ||
            lower.includes('captcha') ||
            lower.includes('turnstile') ||
            lower.includes('geetest') ||
            lower.includes('challenges.cloudflare') ||
            lower.includes('hcaptcha') ||
            lower.includes('recaptcha') ||
            lower.includes('byteoversea') ||
            lower.includes('bytedance')
        );
    }

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
        if (window.__ds_logs.length > 500) {
            window.__ds_logs.shift();
        }
    }

    // 2. Intercept window.fetch (passes through captcha 100% untouched)
    const originalFetch = window.fetch;
    const customFetch = async function fetch(input, init) {
        const url = (typeof input === 'string') ? input : (input && input.url ? input.url : String(input));

        // If captcha or telemetry, DO NOT touch or clone!
        if (isCaptchaOrTelemetry(url)) {
            return originalFetch.apply(this, arguments);
        }

        const method = (init && init.method) || (input && input.method) || 'GET';
        const headers = sanitizeHeaders((init && init.headers) || (input && input.headers));

        checkAuthHeaders(headers);

        let serializedBody = null;
        let fileInfo = null;

        if (init && init.body) {
            if (typeof init.body === 'string') {
                try { serializedBody = JSON.parse(init.body); } catch (e) { serializedBody = init.body; }
            } else if (init.body instanceof FormData) {
                serializedBody = {};
                fileInfo = [];
                for (const [key, val] of init.body.entries()) {
                    if (val instanceof File || val instanceof Blob) {
                        const info = { field: key, name: val.name || 'blob', size: val.size, type: val.type };
                        fileInfo.push(info);
                        serializedBody[key] = info;
                    } else {
                        serializedBody[key] = val;
                    }
                }
            }
        }

        const reqId = Math.random().toString(36).substring(2, 9);
        pushLog({
            id: reqId,
            type: 'fetch',
            kind: 'request',
            method: method.toUpperCase(),
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
                    method: method.toUpperCase(),
                    url: url,
                    status: clone.status,
                    statusText: clone.statusText,
                    headers: resHeaders
                });
            } else {
                clone.text().then(text => {
                    let body = text;
                    try { body = JSON.parse(text); } catch (e) {}
                    if (body && typeof body === 'object' && body.data && body.data.token) {
                        window.__ds_auth_captured.token = body.data.token;
                    }
                    pushLog({
                        id: reqId,
                        type: 'fetch',
                        kind: 'response',
                        method: method.toUpperCase(),
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
                method: method.toUpperCase(),
                url: url,
                error: String(err)
            });
            throw err;
        }
    };
    markNative(customFetch);
    window.fetch = customFetch;

    // 3. Intercept XMLHttpRequest
    const origOpen = XMLHttpRequest.prototype.open;
    const origSend = XMLHttpRequest.prototype.send;
    const origSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;

    const customOpen = function open(method, url, ...rest) {
        if (!isCaptchaOrTelemetry(url)) {
            this.__ds_data = {
                id: Math.random().toString(36).substring(2, 9),
                type: 'xhr',
                method: (method || 'GET').toUpperCase(),
                url: String(url),
                headers: {}
            };
        }
        return origOpen.apply(this, [method, url, ...rest]);
    };
    markNative(customOpen);
    XMLHttpRequest.prototype.open = customOpen;

    const customSetRequestHeader = function setRequestHeader(header, value) {
        if (this.__ds_data && this.__ds_data.headers) {
            this.__ds_data.headers[header.toLowerCase()] = value;
            checkAuthHeaders(this.__ds_data.headers);
        }
        return origSetRequestHeader.apply(this, arguments);
    };
    markNative(customSetRequestHeader);
    XMLHttpRequest.prototype.setRequestHeader = customSetRequestHeader;

    const customSend = function send(body) {
        if (this.__ds_data) {
            let serializedBody = body;
            if (typeof body === 'string') {
                try { serializedBody = JSON.parse(body); } catch (e) {}
            }
            pushLog({
                id: this.__ds_data.id,
                type: 'xhr',
                kind: 'request',
                method: this.__ds_data.method,
                url: this.__ds_data.url,
                headers: this.__ds_data.headers,
                body: serializedBody
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
    markNative(customSend);
    XMLHttpRequest.prototype.send = customSend;

    console.log('[Interceptor] Protected network logger active.');
})();
