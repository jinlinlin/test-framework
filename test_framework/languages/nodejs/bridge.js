/**
 * Node 端桥接脚本 — 统一入口。
 *
 * 职责：
 *   1. 接收 Python 传入的 JSON 参数（命令行参数）
 *   2. 动态加载指定的 JS 模块/函数
 *   3. 执行模块并将结果以 JSON 格式输出到 stdout
 *
 * 用法：
 *   node bridge.js --module=./api_load_test.js --args='{"url":"http://..."}'
 *
 * 输出格式（JSON）：
 *   成功：{ "success": true, "data": { ... } }
 *   失败：{ "success": false, "error": "...", "stack": "..." }
 */

'use strict';

const path = require('path');

/**
 * 解析命令行参数（--key=value 格式）。
 * @param {string[]} argv - 命令行参数数组
 * @returns {Object} 解析后的键值对
 */
function parseArgs(argv) {
    const result = {};
    argv.forEach(arg => {
        if (arg.startsWith('--')) {
            const equalIndex = arg.indexOf('=');
            if (equalIndex !== -1) {
                const key = arg.substring(2, equalIndex);
                const value = arg.substring(equalIndex + 1);
                result[key] = value;
            } else {
                result[arg.substring(2)] = true;
            }
        }
    });
    return result;
}

/**
 * 主函数 — 加载并执行指定模块。
 */
async function main() {
    const args = parseArgs(process.argv.slice(2));
    const startTime = Date.now();

    // 验证必要参数
    if (!args.module) {
        console.log(JSON.stringify({
            success: false,
            error: '缺少 --module 参数',
            duration: 0
        }));
        process.exit(1);
    }

    try {
        // 解析模块路径
        const modulePath = path.resolve(args.module);

        // 动态加载模块
        const mod = require(modulePath);

        // 解析传入参数
        const inputArgs = args.args ? JSON.parse(args.args) : {};

        // 执行模块（支持 default export 和 module.exports）
        const handler = mod.default || mod;
        let result;

        if (typeof handler === 'function') {
            result = await handler(inputArgs);
        } else if (typeof handler.run === 'function') {
            result = await handler.run(inputArgs);
        } else {
            result = handler;
        }

        const duration = Date.now() - startTime;

        // 输出成功结果
        console.log(JSON.stringify({
            success: true,
            data: result,
            duration: duration
        }));

    } catch (error) {
        const duration = Date.now() - startTime;

        // 输出错误结果
        console.log(JSON.stringify({
            success: false,
            error: error.message || String(error),
            stack: error.stack || '',
            duration: duration
        }));
        process.exit(1);
    }
}

// 执行主函数
main().catch(error => {
    console.log(JSON.stringify({
        success: false,
        error: error.message || '未知错误',
        stack: error.stack || ''
    }));
    process.exit(1);
});
