/**
 * Node.js 主入口 — 根据测试类型调用对应的测试引擎。
 *
 * 用法：node run.js --type=api --config='{"url":"http://..."}'
 *
 * @module run
 */

const { ApiLoadTest } = require('./api_load_test');
const { WebSocketTest } = require('./websocket_test');
const { GrpcTest } = require('./grpc_test');

/**
 * 解析命令行参数。
 * @param {string[]} argv - 命令行参数数组。
 * @returns {Object} 解析后的参数对象。
 */
function parseArgs(argv) {
    const args = {};
    for (const arg of argv) {
        if (arg.startsWith('--')) {
            const [key, ...rest] = arg.slice(2).split('=');
            args[key] = rest.length > 0 ? rest.join('=') : true;
        }
    }
    return args;
}

/** 测试类型 -> 引擎类映射 */
const ENGINES = {
    api: ApiLoadTest,
    websocket: WebSocketTest,
    grpc: GrpcTest,
};

/**
 * 主函数。
 */
async function main() {
    const args = parseArgs(process.argv.slice(2));
    const type = args.type || 'api';

    const Engine = ENGINES[type];
    if (!Engine) {
        console.error(`不支持的测试类型: ${type}`);
        console.error(`可用类型: ${Object.keys(ENGINES).join(', ')}`);
        process.exit(1);
    }

    // 解析配置
    let config = {};
    if (args.config) {
        try {
            config = JSON.parse(args.config);
        } catch (e) {
            console.error(`配置解析失败: ${e.message}`);
            process.exit(1);
        }
    }

    console.log(`[INFO] 启动 ${type} 测试引擎`);
    const engine = new Engine(config);
    const result = await engine.run();

    console.log(JSON.stringify(result, null, 2));
    process.exit(result.success ? 0 : 1);
}

main().catch(err => {
    console.error(`[FATAL] ${err.message}`);
    process.exit(1);
});
