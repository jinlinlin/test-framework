# Node.js 编码规范

## 命名规范
- 文件名：小写 + 下划线（snake_case）或 camelCase，如 `bridge.js`, `apiLoadTest.js`
- 类名：大驼峰（PascalCase），如 `NodeRestAPIEngine`
- 函数/方法：小驼峰（camelCase），如 `executeLoadTest`
- 常量：全大写 + 下划线，如 `MAX_CONCURRENCY`
- 私有成员：以 `#` 前缀（ES2022+）或 `_` 前缀

## JSDoc 注释
所有导出函数、类、方法必须添加 JSDoc 注释：

```javascript
/**
 * 执行 API 负载测试并返回聚合结果。
 *
 * @param {Object} config - 测试配置
 * @param {string} config.url - 目标 URL
 * @param {string} [config.method='GET'] - HTTP 方法
 * @param {number} config.concurrency - 并发数
 * @param {number} config.totalRequests - 总请求数
 * @returns {Promise<Object>} 聚合结果，包含 throughput, latencyAvg, errorRate 等字段
 * @throws {Error} 当目标服务不可达时抛出
 */
async function executeLoadTest(config) { ... }
```

## 模块导出
- 使用 CommonJS（`module.exports`）保证与 Node 16+ 兼容性
- 每个文件仅导出一个主类或一组相关函数

## 错误处理
- 使用 `try/catch` 捕获异步错误
- 使用 `process.on('uncaughtException')` 兜底
- 错误消息包含上下文信息

## 异步编程
- 优先使用 `async/await`
- 并发控制使用 `Promise.allSettled` + Semaphore 模式
- 避免回调嵌套

## JSON 输出
- 所有被 Python 调用的脚本必须通过 `stdout` 输出 JSON 结果
- JSON 格式：`{ "success": true/false, "data": {...}, "error": "..." }`
