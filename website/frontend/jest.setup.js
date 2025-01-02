import '@testing-library/jest-dom';

// Mock Response if it's not available (Node environment)
if (typeof Response === 'undefined') {
  global.Response = class Response {
    constructor(body, init) {
      this.body = body;
      this.headers = new Map(Object.entries(init?.headers || {}));
      this.ok = true;
      this.status = 200;
      this.statusText = 'OK';
    }

    text() {
      return Promise.resolve(this.body);
    }
  };
}
