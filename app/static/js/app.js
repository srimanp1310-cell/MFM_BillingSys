// App-wide JS: service worker registration + Web Push subscription.

(function () {
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('/service-worker.js').catch((e) => console.warn('SW registration failed', e));

  const bell = document.getElementById('pushBell');
  const vapidMeta = document.querySelector('meta[name="vapid-key"]');
  const vapidKey = vapidMeta ? vapidMeta.content : '';
  if (!bell || !vapidKey || !('PushManager' in window) || !('Notification' in window)) return;

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
  }

  function setBellState(subscribed) {
    bell.querySelector('i').className = subscribed ? 'bi bi-bell-fill' : 'bi bi-bell';
    bell.title = subscribed ? 'Low-stock notifications ON (tap to disable)' : 'Enable low-stock notifications';
  }

  async function getSubscription() {
    const reg = await navigator.serviceWorker.ready;
    return reg.pushManager.getSubscription();
  }

  async function init() {
    bell.hidden = false;
    setBellState(!!(await getSubscription()));
  }

  bell.addEventListener('click', async () => {
    const reg = await navigator.serviceWorker.ready;
    const existing = await reg.pushManager.getSubscription();
    const csrf = document.querySelector('meta[name="csrf-token"]').content;

    if (existing) {
      await fetch('/push/unsubscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ endpoint: existing.endpoint }),
      });
      await existing.unsubscribe();
      setBellState(false);
      return;
    }

    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return;
    try {
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      });
      const resp = await fetch('/push/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify(sub.toJSON()),
      });
      const data = await resp.json();
      setBellState(!!data.ok);
    } catch (e) {
      console.warn('Push subscribe failed', e);
    }
  });

  init();
})();
