/**
 * REST API 测试引擎 — Node.js 高并发引擎。
 *
 * 职责：基于 axios + 并发信号量实现高吞吐量接口压测。
 *       被 Python 通过 LanguageBridge (IPCBridge) 调度。
 *
 * 使用方式：
 *   node engine.js --config '{"url":"http://example.com/api","method":"GET","concurrency":10,"totalRequests":100}'
 *
 * 输出：JSON 格式的聚合测试结果到 stdout。
 */

'use strict';

const http = require('http');
const https = require('https');
const { URL } = require('url');

/**
 * 并发信号量 — 控制同时执行的请求数。
 *
 * @class Semaphore
 */
class Semaphore {
    /**
     * @param {number} max - 最大并发数。
     */
    constructor(max) {
        this._max = max;
        this._current = 0;
        this._queue = [];
    }

    /**
     * 获取信号量，若已达上限则等待。
     * @returns {Promise<void>}
     */
    acquire() {
        if (this._current < this._max) {
            this._current++;
            return Promise.resolve();
        }
        return new Promise((resolve) => {
            this._queue.push(resolve);
        });
    }

    /**
     * 释放信号量，允许下一个等待的请求执行。
     */
    release() {
        this._current--;
        if (this._queue.length > 0) {
            this._current++;
            const next = this._queue.shift();
            next();
        }
    }
}

/**
 * Node.js REST API 测试引擎。
 *
 * 支持高并发压测，通过信号量控制并发数，
 * 聚合所有请求结果后输出统计指标。
 *
 * @class NodeRestAPIEngine
 */
class NodeRestAPIEngine {
    /**
     * @param {Object} config - 引擎配置。
     * @param {number} [config.timeout=30000] - 单请求超时（毫秒）。
     * @param {boolean} [config.verifySSL=true] - 是否验证 SSL。
     */
    constructor(config = {}) {
        this.config = config;
        this.timeout = config.timeout || 30000;
        this.verifySSL = config.verifySSL !== false;
        this.results = [];
    }

    /**
     * 执行并发压测。
     *
     * @param {Object} params - 压测参数。
     * @param {string} params.url - 目标 URL。
     * @param {string} [params.method='GET'] - HTTP 方法。
     * @param {Object} [params.headers={}] - 请求头。
     * @param {*} [params.body=null] - 请求体。
     * @param {number} [params.concurrency=10] - 并发数。
     * @param {number} [params.totalRequests=100] - 总请求数。
     * @param {number} [params.duration=0] - 压测持续时间（秒），0 表示不限。
     * @returns {Promise<Object>} 聚合结果。
     */
    async execute({ url, method = 'GET', headers = {}, body = null,
                    concurrency = 10, totalRequests = 100, duration = 0 }) {
        const semaphore = new Semaphore(concurrency);
        const tasks = [];
        let completed = 0;
        let errors = 0;
        const startTime = Date.now();
        const durations = [];
        const statusCodes = [];

        // 压测循环：按并发调度请求
        while (completed < totalRequests) {
            // 检查时间限制
            if (duration > 0 && (Date.now() - startTime) >= duration * 1000) {
                break;
            }

            await semaphore.acquire();

            const taskStart = Date.now();
            tasks.push(
                this._sendRequest(url, method, headers, body)
                    .then((result) => {
                        const elapsed = Date.now() - taskStart;
                        durations.push(elapsed);
                        statusCodes.push(result.statusCode);
                        if (result.error) {
                            errors++;
                        }
                        return result;
                    })
                    .catch((err) => {
                        const elapsed = Date.now() - taskStart;
                        durations.push(elapsed);
                        statusCodes.push(0);
                        errors++;
                        return { error: err.message };
                    })
                    .finally(() => {
                        completed++;
                        semaphore.release();
                    })
            );
        }

        // 等待所有请求完成
        await Promise.allSettled(tasks);
        const totalTime = Date.now() - startTime;

        return this._aggregate(durations, statusCodes, errors, totalTime, completed);
    }

    /**
     * 发送单个 HTTP 请求。
     *
     * @param {string} url - 请求 URL。
     * @param {string} method - HTTP 方法。
     * @param {Object} headers - 请求头。
     * @param {*} body - 请求体。
     * @returns {Promise<Object>} 响应结果。
     * @private
     */
    _sendRequest(url, method, headers, body) {
        return new Promise((resolve, reject) => {
            const parsedUrl = new URL(url);
            const isHttps = parsedUrl.protocol === 'https:';
            const transport = isHttps ? https : http;

            const options = {
                hostname: parsedUrl.hostname,
                port: parsedUrl.port || (isHttps ? 443 : 80),
                path: parsedUrl.pathname + parsedUrl.search,
                method: method.toUpperCase(),
                headers: { ...headers },
                timeout: this.timeout,
                rejectUnauthorized: this.verifySSL,
            };

            // 设置请求体
            let bodyData = null;
            if (body && ['POST', 'PUT', 'PATCH'].includes(options.method)) {
                bodyData = typeof body === 'string' ? body : JSON.stringify(body);
                options.headers['Content-Type'] = options.headers['Content-Type'] || 'application/json';
                options.headers['Content-Length'] = Buffer.byteLength(bodyData);
            }

            const req = transport.request(options, (res) => {
                let data = '';
                res.on('data', (chunk) => { data += chunk; });
                res.on('end', () => {
                    resolve({
                        statusCode: res.statusCode,
                        headers: res.headers,
                        body: data,
                        error: null,
                    });
                });
            });

            req.on('error', (err) => {
                reject(err);
            });

            req.on('timeout', () => {
                req.destroy();
                reject(new Error('请求超时'));
            });

            if (bodyData) {
                req.write(bodyData);
            }
            req.end();
        });
    }

    /**
     * 聚合所有请求结果，计算统计指标。
     *
     * @param {number[]} durations - 每个请求的耗时（毫秒）。
     * @param {number[]} statusCodes - 每个请求的状态码。
     * @param {number} errors - 错误请求数。
     * @param {number} totalTime - 总耗时（毫秒）。
     * @param {number} totalRequests - 总请求数。
     * @returns {Object} 聚合结果。
     * @private
     */
    _aggregate(durations, statusCodes, errors, totalTime, totalRequests) {
        if (durations.length === 0) {
            return {
                totalRequests: 0,
                errors: 0,
                successRate: 0,
                totalTime: 0,
                avgLatency: 0,
                minLatency: 0,
                maxLatency: 0,
                p50: 0,
                p95: 0,
                p99: 0,
                qps: 0,
                statusCodes: {},
            };
        }

        // 排序计算百分位数
        const sorted = [...durations].sort((a, b) => a - b);
        const p50 = sorted[Math.floor(sorted.length * 0.50)];
        const p95 = sorted[Math.floor(sorted.length * 0.95)];
        const p99 = sorted[Math.floor(sorted.length * 0.99)];

        const avg = durations.reduce((a, b) => a + b, 0) / durations.length;
        const qps = totalRequests / (totalTime / 1000);

        // 统计状态码分布
        const statusCodeDist = {};
        for (const code of statusCodes) {
            statusCodeDist[code] = (statusCodeDist[code] || 0) + 1;
        }

        return {
            totalRequests,
            errors,
            successRate: ((totalRequests - errors) / totalRequests * 100).toFixed(2),
            totalTime,
            avgLatency: Math.round(avg * 100) / 100,
            minLatency: sorted[0],
            maxLatency: sorted[sorted.length - 1],
            p50,
            p95,
            p99,
            qps: Math.round(qps * 100) / 100,
            statusCodes: statusCodeDist,
        };
    }
}

// ===== CLI 入口 =====
if (require.main === module) {
    const args = process.argv.slice(2);
    let config = {};
    let params = {};

    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--config' && args[i + 1]) {
            try {
                config = JSON.parse(args[i + 1]);
            } catch (e) {
                console.error(JSON.stringify({ error: '无效的 config JSON' }));
                process.exit(1);
            }
            i++;
        }
        if (args[i] === '--params' && args[i + 1]) {
            try {
                params = JSON.parse(args[i + 1]);
            } catch (e) {
                console.error(JSON.stringify({ error: '无效的 params JSON' }));
                process.exit(1);
            }
            i++;
        }
    }

    // 合并 config 和 params（params 优先）
    const mergedParams = { ...config, ...params };

    const engine = new NodeRestAPIEngine(config);
    engine.execute(mergedParams)
        .then((result) => {
            process.stdout.write(JSON.stringify(result));
        })
        .catch((err) => {
            process.stderr.write(JSON.stringify({ error: err.message }));
            process.exit(1);
        });
}

module.exports = NodeRestAPIEngine;
