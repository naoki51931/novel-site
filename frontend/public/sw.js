self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

function buildNotificationTitle(baseTitle, count) {
  if (count <= 1) return baseTitle;
  return `${baseTitle} (${count}件)`;
}

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : "" };
  }

  event.waitUntil(
    (async () => {
      const groupTag = data.tag || "site-notification";
      const active = await self.registration.getNotifications();
      const sameGroupCount = active.filter(
        (n) => n?.data?.groupTag === groupTag
      ).length;
      const nextCount = sameGroupCount + 1;
      const title = buildNotificationTitle(data.title || "通知", nextCount);
      const uniqueTag = `${groupTag}-${Date.now()}-${Math.random()
        .toString(36)
        .slice(2, 8)}`;

      const options = {
        body: data.body || "",
        icon: "/favicon.png",
        badge: "/favicon.png",
        // 通知を上書きせず、複数枠で表示する
        tag: uniqueTag,
        renotify: true,
        data: {
          url: data.url || "/notifications",
          groupTag,
          count: nextCount,
        },
      };

      await self.registration.showNotification(title, options);
    })()
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification?.data?.url || "/notifications";
  event.waitUntil(
    (async () => {
      const list = await clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of list) {
        if ("focus" in client) {
          await client.focus();
          if ("navigate" in client) {
            await client.navigate(targetUrl);
          }
          return;
        }
      }
      if (clients.openWindow) {
        await clients.openWindow(targetUrl);
      }
    })()
  );
});
