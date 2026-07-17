/**
 * 性能工作器 — 被 Python IPC 调度的后台 worker。
 *
 * 常驻运行，通过 stdin/stdout JSON 协议接收任务并返回结果。
 *
 * 协议格式：
 *   请求: {"id": "task-001", "type": "cpu_bench|http_bench|...", "params": {...}}
 *   响应: {"id": "task-001", "result": {...}, "error": null}
 *
 * @module performance_worker
 */

const { performance } = require('perf_hooks');
const readline = require('readline');

/**
 * CPU 基准测试。
 * @param {Object} params - { iterations: number }
 * @returns {Object} { duration_ms, ops_per_sec }
 */
function cpuBenchmark(params = {}) {
    const iterations = params.iterations || 1000000;
    const start = performance.now();

    let result = 0;
    for (let i = 0; i < iterations; i++) {
        result += Math.sqrt(i) * Math.sin(i);
    }

    const duration = performance.now() - start;
    return {
        duration_ms: duration.toFixed(2),
        ops_per_sec: (iterations / (duration / 1000)).toFixed(0),
        result: result, // 防止死代码消除
    };
}

/**
 * 内存压力测试。
 * @param {Object} params - { size_mb: number }
 * @returns {Object} { allocated_mb, duration_ms }
 */
function memoryBenchmark(params = {}) {
    const sizeMb = params.size_mb || 100;
    const start = performance.now();

    // 分配指定大小的 Buffer
    const buffer = Buffer.alloc(sizeMb * 1024 * 1024, 'x');
    const duration = performance.now() - start;

    return {
        allocated_mb: sizeMb,
        duration_ms: duration.toFixed(2),
        checksum: buffer.length,
    };
}

/**
 * 简单 HTTP 请求基准。
 * @param {Object} params - { url, count }
 * @returns {Promise<Object>}
 */
async function httpBenchmark(params = {}) {
    const url = params.url || 'http://localhost:8080';
    const count = params.count || 100;
    const http = require('http');

    const latencies = [];
    for (let i = 0; i < count; i++) {
        const start = performance.now();
        await new Promise((resolve, reject) => {
            http.get(url, (res) => {
                res.resume();
                res.on('end', resolve);
            }).on('error', reject);
        }).catch(() => {});
        latencies.push(performance.now() - start);
    }

    latencies.sort((a, b) => a - b);
    return {
        url,
        count,
        avg_ms: (latencies.reduce((a, b) => a + b, 0) / latencies.length).toFixed(2),
        p95_ms: latencies[Math.floor(latencies.length * 0.95)].toFixed(2),
    };
}

/** 任务类型 -> 处理函数映射 */
const HANDLERS = {
    cpu_bench: cpuBenchmark,
    memory_bench: memoryBenchmark,
    http_bench: httpBenchmark,
};

/**
 * 主循环 — 从 stdin 读取 JSON 任务，执行后通过 stdout 返回结果。
 */
function main() {
    const rl = readline.createInterface({ input: process.stdin });

    console.error('[performance_worker] 已启动，等待任务...');

    rl.on('line', async (line) => {
        let task;
        try {
            task = JSON.parse(line);
        } catch (e) {
            console.log(JSON.stringify({ error: 'JSON 解析失败: ' + e.message }));
            return;
        }

        const handler = HANDLERS[task.type];
        if (!handler) {
            console.log(JSON.stringify({
                id: task.id,
                error: `未知任务类型: ${task.type}`,
            }));
            return;
        }

        try {
            const result = await handler(task.params || {});
            console.log(JSON.stringify({ id: task.id, result, error: null }));
        } catch (err) {
            console.log(JSON.stringify({ id: task.id, result: null, error: err.message }));
        }
    });

    rl.on('close', () => {
        console.error('[performance_worker] 已关闭');
        process.exit(0);
    });
}

// 启动
main();
