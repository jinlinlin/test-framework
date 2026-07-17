/**
 * 日志工具 (Node.js) — 提供统一的日志格式化和级别控制。
 *
 * 支持控制台彩色输出、文件日志、JSON 结构化日志。
 *
 * @module logger
 */

const fs = require('fs');
const path = require('path');

/** 日志级别枚举 */
const LOG_LEVELS = {
    DEBUG: 0,
    INFO: 1,
    WARN: 2,
    ERROR: 3,
    FATAL: 4,
};

/** ANSI 颜色代码 */
const COLORS = {
    DEBUG: '\x1b[36m',   // 青色
    INFO: '\x1b[32m',    // 绿色
    WARN: '\x1b[33m',    // 黄色
    ERROR: '\x1b[31m',   // 红色
    FATAL: '\x1b[35m',   // 紫色
    RESET: '\x1b[0m',
};

/**
 * Logger 类 — 统一日志管理。
 *
 * @example
 * const logger = new Logger('MyModule', { level: 'DEBUG', file: 'app.log' });
 * logger.info('服务已启动');
 */
class Logger {
    /**
     * @param {string} name - 模块名称。
     * @param {Object} [options] - 配置选项。
     * @param {string} [options.level='INFO'] - 日志级别。
     * @param {string|null} [options.file=null] - 日志文件路径。
     * @param {boolean} [options.json=false] - 是否使用 JSON 格式。
     * @param {boolean} [options.color=true] - 是否使用彩色输出。
     */
    constructor(name, options = {}) {
        this.name = name;
        this.level = LOG_LEVELS[options.level || 'INFO'];
        this.json = options.json || false;
        this.color = options.color !== false;
        this.stream = null;

        if (options.file) {
            const dir = path.dirname(options.file);
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
            this.stream = fs.createWriteStream(options.file, { flags: 'a' });
        }
    }

    /**
     * 格式化日志条目。
     * @private
     * @param {string} level - 日志级别名称。
     * @param {string} message - 日志消息。
     * @param {Object} [extra] - 额外字段。
     * @returns {string} 格式化后的日志字符串。
     */
    _format(level, message, extra = {}) {
        const timestamp = new Date().toISOString();
        if (this.json) {
            return JSON.stringify({
                timestamp,
                level,
                module: this.name,
                message,
                ...extra,
            });
        }
        const color = this.color ? (COLORS[level] || '') : '';
        const reset = this.color ? COLORS.RESET : '';
        return `${timestamp} | ${color}${level.padEnd(5)}${reset} | ${this.name} | ${message}`;
    }

    /**
     * 输出日志到控制台和文件。
     * @private
     * @param {string} level - 日志级别。
     * @param {string} message - 消息。
     * @param {Object} [extra] - 额外数据。
     */
    _log(level, message, extra) {
        if (LOG_LEVELS[level] < this.level) return;
        const formatted = this._format(level, message, extra);

        // 控制台输出
        if (level === 'ERROR' || level === 'FATAL') {
            console.error(formatted);
        } else {
            console.log(formatted);
        }

        // 文件输出
        if (this.stream) {
            this.stream.write(this._format(level, message, extra) + '\n');
        }
    }

    /** @param {string} msg - 调试消息 */
    debug(msg, extra) { this._log('DEBUG', msg, extra); }

    /** @param {string} msg - 信息消息 */
    info(msg, extra) { this._log('INFO', msg, extra); }

    /** @param {string} msg - 警告消息 */
    warn(msg, extra) { this._log('WARN', msg, extra); }

    /** @param {string} msg - 错误消息 */
    error(msg, extra) { this._log('ERROR', msg, extra); }

    /** @param {string} msg - 致命错误消息 */
    fatal(msg, extra) { this._log('FATAL', msg, extra); }

    /** 关闭文件流 */
    close() {
        if (this.stream) {
            this.stream.end();
            this.stream = null;
        }
    }
}

module.exports = { Logger, LOG_LEVELS };
