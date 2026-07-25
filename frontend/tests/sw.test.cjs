const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

// Path to sw.js
const swPath = path.join(__dirname, '../public/sw.js');
const swCode = fs.readFileSync(swPath, 'utf8');

// Mock service worker environment
const listeners = {};
const mockShowNotificationCalls = [];
const mockOpenWindowCalls = [];
const mockClosedNotifications = [];

const mockSelf = {
  addEventListener(event, callback) {
    listeners[event] = callback;
  },
  registration: {
    showNotification(title, options) {
      mockShowNotificationCalls.push({ title, options });
      return Promise.resolve();
    }
  },
  clients: {
    matchAll(options) {
      // Simulate no open windows for simplicity, which triggers openWindow
      return Promise.resolve([]);
    },
    openWindow(url) {
      mockOpenWindowCalls.push(url);
      return Promise.resolve({
        focus: () => Promise.resolve()
      });
    }
  }
};

// Create a sandbox context
const context = vm.createContext({
  self: mockSelf,
  console: console,
  setTimeout,
  clearTimeout,
});

// Run sw.js in the context
vm.runInContext(swCode, context);

// Helpers to trigger events
function triggerPushEvent(dataText, isJson = true) {
  const event = {
    data: {
      json() {
        if (!isJson) throw new Error('Malformed JSON');
        return JSON.parse(dataText);
      }
    },
    waitUntil(promise) {
      this.promise = promise;
    }
  };
  
  if (listeners['push']) {
    listeners['push'](event);
    return event.promise || Promise.resolve();
  }
  return Promise.resolve();
}

function triggerNotificationClickEvent(url) {
  const event = {
    notification: {
      data: { url },
      close() {
        mockClosedNotifications.push(this);
      }
    },
    waitUntil(promise) {
      this.promise = promise;
    }
  };
  
  if (listeners['notificationclick']) {
    listeners['notificationclick'](event);
    return event.promise || Promise.resolve();
  }
  return Promise.resolve();
}

async function runTests() {
  console.log('Running Service Worker Unit Tests...');

  // Test 1: Push event with valid JSON
  mockShowNotificationCalls.length = 0;
  await triggerPushEvent('{"title": "Test Title", "body": "Test Body", "url": "/calendar"}');
  assert.strictEqual(mockShowNotificationCalls.length, 1);
  assert.strictEqual(mockShowNotificationCalls[0].title, 'Test Title');
  assert.strictEqual(mockShowNotificationCalls[0].options.body, 'Test Body');
  assert.strictEqual(mockShowNotificationCalls[0].options.data.url, '/calendar');
  console.log('✅ Push event with valid JSON test passed');

  // Test 2: Push event with malformed JSON
  mockShowNotificationCalls.length = 0;
  await triggerPushEvent('invalid-json', false);
  assert.strictEqual(mockShowNotificationCalls.length, 1);
  assert.strictEqual(mockShowNotificationCalls[0].title, 'period.');
  assert.strictEqual(mockShowNotificationCalls[0].options.body, 'Check your cycle update');
  console.log('✅ Push event with malformed JSON fallback test passed');

  // Test 3: Notification click event opens the correct window URL
  mockOpenWindowCalls.length = 0;
  mockClosedNotifications.length = 0;
  await triggerNotificationClickEvent('/calendar');
  assert.strictEqual(mockClosedNotifications.length, 1);
  assert.strictEqual(mockOpenWindowCalls.length, 1);
  assert.strictEqual(mockOpenWindowCalls[0], '/calendar');
  console.log('✅ Notification click event opens the correct window URL test passed');

  console.log('🎉 All Service Worker Unit Tests passed successfully!');
}

runTests().catch(err => {
  console.error('❌ Service Worker Unit Test failed:', err);
  process.exit(1);
});
