/* pywebview-shim.js
   Drop-in replacement for the pywebview JS bridge.
   The original desktop app called window.pywebview.api.<method>(...args)
   and pywebview handled the Python call natively. On the web, this shim
   makes the exact same calls hit POST /api/<method> on the Flask server,
   so app.js did not need to change at all.
*/
(function () {
  window.pywebview = window.pywebview || {};

  window.pywebview.api = new Proxy({}, {
    get(_target, methodName) {
      return async (...args) => {
        const res = await fetch(`/api/${methodName}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ args }),
        });

        if (res.status === 401) {
          window.location.href = "/login";
          return null;
        }

        if (!res.ok) {
          const text = await res.text().catch(() => "");
          console.error(`API call to ${String(methodName)} failed:`, text);
          throw new Error(`Request failed (${res.status})`);
        }

        return res.json();
      };
    },
  });
})();
