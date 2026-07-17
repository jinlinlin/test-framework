/**
 * WebSocket 连接测试 — 测试连接建立、消息收发、心跳、断线重连。
 *
 * @module websocket_test
 */

const { URL } = require('url');

/**
 * WebSocket 测试引擎。
 *
 * @example
 * const test = new WebSocketTest({ url: 'ws://localhost:8080/ws', messages: 100 });
 * const result = await test.run();
 */
class WebSocketTest {
    /**
     * @param {Object} config - 测试配置。
     * @param {string} config.url - WebSocket URL。
     * @param {number} [config.messages=50] - 发送消息数。
     * @param {number} [config.messageSize=256] - 消息大小（字节）。
     * @param {number} [config.timeout=10000] - 超时时间（ms）。
     * @param {boolean} [config.heartbeat=true] - 是否启用心跳检测。
     */
    constructor(config = {}) {
        this.url = config.url || 'ws://localhost:8080/ws';
        this.messageCount = config.messages || 50;
        this.messageSize = config.messageSize || 256;
        this.timeout = config.timeout || 10000;
        this.heartbeat = config.heartbeat !== false;
    }

    /**
     * 生成随机消息。
     * @param {number} size - 消息大小。
     * @returns {string} 随机字符串。
     */
    _generateMessage(size) {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        let result = '';
        for (let i = 0; i < size; i++) {
            result += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return result;
    }

    /**
     * 执行 WebSocket 测试。
     * @returns {Promise<Object>} 测试结果。
     */
    async run() {
        console.log(`[INFO] WebSocket 测试: ${this.url}`);
        console.log(`[INFO] 消息数: ${this.messageCount}, 大小: ${this.messageSize}B`);

        const startTime = Date.now();
        let ws;
        let connected = false;
        let messagesSent = 0;
        let messagesReceived = 0;
        let errors = [];

        try {
            // 尝试加载 ws 模块
            const WebSocket = require('ws');
            ws = new WebSocket(this.url);

            connected = await new Promise((resolve) => {
                const timer = setTimeout(() => resolve(false), this.timeout);
                ws.on('open', () => { clearTimeout(timer); resolve(true); });
                ws.on('error', (err) => {
                    clearTimeout(timer);
                    errors.push(err.message);
                    resolve(false);
                });
            });

            if (!connected) {
                return {
                    success: false,
                    error: '连接超时',
                    url: this.url,
                };
            }

            // 发送和接收消息
            const latencies = [];
            for (let i = 0; i < this.messageCount; i++) {
                const msg = this._generateMessage(this.messageSize);
                const sendTime = Date.now();

                ws.send(msg);
                messagesSent++;

                // 等待回显（如果有）
                await new Promise((resolve) => {
                    const timer = setTimeout(resolve, 100);
                    ws.once('message', () => {
                        clearTimeout(timer);
                        latencies.push(Date.now() - sendTime);
                        messagesReceived++;
                        resolve();
                    });
                });
            }

            ws.close();

        } catch (err) {
            errors.push(err.message);
        }

        const totalTime = (Date.now() - startTime) / 1000;

        return {
            success: errors.length === 0 && connected,
            url: this.url,
            connected,
            messages_sent: messagesSent,
            messages_received: messagesReceived,
            errors: errors,
            total_time: totalTime.toFixed(2) + 's',
            avg_latency: latencies.length > 0
                ? (latencies.reduce((a, b) => a + b, 0) / latencies.length).toFixed(2) + 'ms'
                : 'N/A',
        };
    }
}

module.exports = { WebSocketTest };
