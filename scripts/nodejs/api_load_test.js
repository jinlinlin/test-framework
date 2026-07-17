/**
 * 高并发 API 负载测试 — 使用原生 HTTP 模块实现并发请求。
 *
 * @module api_load_test
 */

const http = require('http');
const https = require('https');
const { URL } = require('url');

/**
 * API 负载测试引擎。
 *
 * @example
 * const test = new ApiLoadTest({ url: 'http://localhost:8080/api', concurrency: 50, total: 1000 });
 * const result = await test.run();
 */
class ApiLoadTest {
    /**
     * @param {Object} config - 测试配置。
     * @param {string} config.url - 目标 URL。
     * @param {string} [config.method='GET'] - HTTP 方法。
     * @param {Object} [config.headers={}] - 请求头。
     * @param {string} [config.body=null] - 请求体。
     * @param {number} [config.concurrency=10] - 并发数。
     * @param {number} [config.total=100] - 总请求数。
     * @param {number} [config.timeout=30000] - 超时时间（ms）。
     */
    constructor(config = {}) {
        this.url = config.url || 'http://localhost:8080';
        this.method = (config.method || 'GET').toUpperCase();
        this.headers = config.headers || {};
        this.body = config.body || null;
        this.concurrency = config.concurrency || 10;
        this.total = config.total || 100;
        this.timeout = config.timeout || 30000;
    }

    /**
     * 发送单个 HTTP 请求。
     * @returns {Promise<{status: number, latency: number, error: string|null}>}
     */
    _sendRequest() {
        return new Promise((resolve) => {
            const start = Date.now();
            const parsed = new URL(this.url);
            const client = parsed.protocol === 'https:' ? https : http;

            const options = {
                hostname: parsed.hostname,
                port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
                path: parsed.pathname + parsed.search,
                method: this.method,
                headers: this.headers,
                timeout: this.timeout,
            };

            const req = client.request(options, (res) => {
                let data = '';
                res.on('data', (chunk) => { data += chunk; });
                res.on('end', () => {
                    resolve({
                        status: res.statusCode,
                        latency: Date.now() - start,
                        error: null,
                    });
                });
            });

            req.on('error', (err) => {
                resolve({ status: 0, latency: Date.now() - start, error: err.message });
            });

            req.on('timeout', () => {
                req.destroy();
                resolve({ status: 0, latency: this.timeout, error: 'timeout' });
            });

            if (this.body) {
                req.write(this.body);
            }
            req.end();
        });
    }

    /**
     * 执行负载测试。
     * @returns {Promise<Object>} 测试结果。
     */
    async run() {
        console.log(`[INFO] API 负载测试: ${this.method} ${this.url}`);
        console.log(`[INFO] 并发: ${this.concurrency}, 总量: ${this.total}`);

        const results = [];
        const startTime = Date.now();
        let completed = 0;

        // 分批并发
        for (let i = 0; i < this.total; i += this.concurrency) {
            const batchSize = Math.min(this.concurrency, this.total - i);
            const batch = Array.from({ length: batchSize }, () => this._sendRequest());
            const batchResults = await Promise.all(batch);
            results.push(...batchResults);
            completed += batchSize;
            if (completed % 100 === 0 || completed === this.total) {
                console.log(`[INFO] 进度: ${completed}/${this.total}`);
            }
        }

        const totalTime = (Date.now() - startTime) / 1000;
        const latencies = results.map(r => r.latency).sort((a, b) => a - b);
        const errors = results.filter(r => r.error);
        const successes = results.filter(r => !r.error && r.status >= 200 && r.status < 400);

        return {
            success: errors.length === 0,
            total_requests: this.total,
            success_count: successes.length,
            error_count: errors.length,
            error_rate: (errors.length / this.total * 100).toFixed(2) + '%',
            total_time: totalTime.toFixed(2) + 's',
            throughput: (this.total / totalTime).toFixed(2) + ' req/s',
            latency: {
                avg: (latencies.reduce((a, b) => a + b, 0) / latencies.length).toFixed(2) + 'ms',
                min: latencies[0] + 'ms',
                max: latencies[latencies.length - 1] + 'ms',
                p50: latencies[Math.floor(latencies.length * 0.5)] + 'ms',
                p95: latencies[Math.floor(latencies.length * 0.95)] + 'ms',
                p99: latencies[Math.floor(latencies.length * 0.99)] + 'ms',
            },
        };
    }
}

module.exports = { ApiLoadTest };
