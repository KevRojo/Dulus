/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 * 
 * This script is used to intercept fetch requests to Google Cloud AI APIs and 
 * proxy them to the local Node JS server backend server.
 */
(function() {
  const originalFetch = window.fetch;
  const originalWebSocket = window.WebSocket;

  // Function to validate VertexGenAi endpoints
  function isValidUrl(url) {
    try {
      const HOST_NAME = 'aiplatform.googleapis.com';
      const MODEL_METHODS = ['generateContent', 'predict', 'streamGenerateContent'];
      const AGENT_METHODS = ['query', 'streamQuery'];
      const isSafePathSegment = (val) => val && encodeURIComponent(val) === val;

      const urlObj = new URL(url);
      if (!urlObj.hostname.endsWith(HOST_NAME)) {
        return false;
      }

      const pathSegments = urlObj.pathname.split('/');
      // Publisher models
      // Expected structure: ['', '{version}', 'publishers', 'google', 'models', '{model}:{method}']
      if (pathSegments.length === 6 &&
        pathSegments[0] === '' &&
        pathSegments[2] === 'publishers' &&
        pathSegments[3] === 'google' &&
        pathSegments[4] === 'models' && urlObj.hostname === HOST_NAME) {
          if (!isSafePathSegment(pathSegments[1])) {
            return false;
          }
          const modelAndMethod = pathSegments[5].split(':');
          return modelAndMethod.length === 2 && isSafePathSegment(modelAndMethod[0]) && MODEL_METHODS.includes(modelAndMethod[1]);
      }

      // Reasoning Engines
      // Expected structrue: ['', '{version}', 'projects', 'locations', 'reasoningEngines', '{id}:{method}']
      if (pathSegments.length === 8 &&
        pathSegments[0] === '' &&
        pathSegments[2] === 'projects' &&
        pathSegments[4] === 'locations' &&
        pathSegments[6] === 'reasoningEngines' && urlObj.hostname.endsWith(`-${HOST_NAME}`)) {
          if (!isSafePathSegment(pathSegments[1]) || !isSafePathSegment(pathSegments[3]) || !isSafePathSegment(pathSegments[5])) {
            return false;
          }
          const idAndMethod = pathSegments[7].split(':');
          return idAndMethod.length === 2 && isSafePathSegment(idAndMethod[0]) && AGENT_METHODS.includes(idAndMethod[1]);
      }

      
      // Live API (WebSocket)
      if (url === 'wss://aiplatform.googleapis.com//ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent') {
        return true;
      }

      return false;
    } catch (e) {
      return false;
    }
  }

  console.log('[Vertex AI Proxy Shim] Initialized. Intercepting for Cloud AI API URLs');

  
  window.WebSocket = function(url, protocols) {
    const inputUrl = typeof url === 'string' ? url : (url instanceof URL ? url.href : null);

    if (inputUrl && isValidUrl(inputUrl)) {
      
      console.log('[Vertex AI Proxy Shim] Intercepted Vertex WebSocket request:', inputUrl);
      const targetUrl = encodeURIComponent(inputUrl);
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const proxyUrl = `${protocol}//${host}/ws-proxy?target=${targetUrl}`;
      return new originalWebSocket(proxyUrl, protocols);
    }
    return new originalWebSocket(url, protocols);
  };

  // Copy propertires to ensure compatibility
  window.WebSocket.prototype = originalWebSocket.prototype;
  window.WebSocket.CONNECTING = originalWebSocket.CONNECTING;
  window.WebSocket.OPEN = originalWebSocket.OPEN;
  window.WebSocket.CLOSING = originalWebSocket.CLOSING;
  window.WebSocket.CLOSED = originalWebSocket.CLOSED;

  window.fetch = async function(url, options) {

    const inputUrl = typeof url === 'string' ? url : (url instanceof Request ? url.url : null);
    const normalizedUrl = (typeof inputUrl === 'string') ? inputUrl.split('?')[0] : null;
    // Check if the URL matches the patterns of Vertex AI APIs.
    if (normalizedUrl && isValidUrl(normalizedUrl)) {
      console.log('[Vertex AI Proxy Shim] Intercepted Vertex API request:', normalizedUrl);
      // Prepare the request details to send to the local Node.js backend.
      const requestDetails = {
        originalUrl: normalizedUrl,
        headers: options?.headers ? Object.fromEntries(new Headers(options.headers).entries()) : {},
        method: options?.method || 'POST',
        // Serialize headers from Headers object or plain object (these should include request auth headers.
        // Pass the body as is. The Node backend will handle parsing.
        body: options?.body,
      };

      try {
        // Make a fetch request to the local Node JS proxy endpoint.
        const proxyFetchOptions = {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            // Add a random header to identify these proxied requests on the Node.js backend.
            'X-App-Proxy': 'pWCPFB0DUm2gltmN6M3DE7lBhpy2TM-A',
          },
          body: JSON.stringify(requestDetails),
        };

        console.log('[Vertex AI Proxy Shim] Fetching from local Node.js backend: /api-proxy');
        const proxyResponse = await fetch('/api-proxy', proxyFetchOptions);

        if (proxyResponse.status === 401) {
            console.error('[Vertex Proxy Shim] Local Node.js backend returned 401. Authentication may be needed.');
            return proxyResponse; // Return the proxy's 401 response.
        }


        if (!proxyResponse.ok) {
          console.error(`[Vertex Proxy Shim] Proxy request to /api-proxy failed with status ${proxyResponse.status}: ${proxyResponse.statusText}`);
          return proxyResponse; // Propagate other non-ok responses from the proxy.
        }

        return proxyResponse;
      } catch (error) {
        console.error('[Vertex AI Proxy Shim] Error fetching from local Node.js backend:', error);
        return new Response(JSON.stringify({
            error: 'Proxying failed',
            details: error.message, name: error.name,
            proxiedUrl: inputUrl
          }),
          {
            status: 503, // Service Unavailable
            statusText: 'Local Proxy Unavailable',
            headers: { 'Content-Type': 'text/plain' },
          }
        );
      }
    } else {
      // If the URL doesn't match the Vertex API regex, use the original window.fetch.
      return originalFetch.apply(this, arguments);
    }
  }
})()
