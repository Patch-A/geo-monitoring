/**
 * dsh-plugin-geo-monitoring — a DeepSeek Harness host plugin that gives the
 * model a GEO (Generative Engine Optimization) monitoring toolkit.
 *
 * What it does:
 *  - registers the `geo-monitor` tool: a structured workflow guide for
 *    sampling AI engines (DeepSeek API + Playwright browser automation),
 *    analyzing mentions/ranks, and generating HTML multi-engine reports;
 *  - the heavy lifting lives in the bundled Python scripts (scripts/*.py)
 *    which the agent runs in its shell; this tool tells it exactly how.
 *
 * Mount it in a profile patch or agent preset:
 *   - id: geo-monitoring
 *     name: dsh-plugin-geo-monitoring
 *
 * The tool is pure guidance (no live service dependency): it reads an
 * optional workspace path or defaults to the current directory, and returns
 * a plain JSON workflow description. The model then executes the scripts.
 *
 * @module dsh-plugin-geo-monitoring
 */

/** Stable Cordis plugin name. */
const name = "geo-monitoring";
/** Hard dependency: the tool registry. */
const inject = ["tools"];

/** Map of workflow steps to the bundled scripts. */
const WORKFLOW = {
	sample_deepseek: {
		description: "Run DeepSeek API sampling over the 60-question set (web search enabled).",
		script: "geosample_deepseek.py",
		examples: [
			"python geosample_deepseek.py --limit 6",
			"python geosample_deepseek.py",
			"python geosample_deepseek.py --resume"
		],
		env: ["DEEPSEEK_API_KEY"]
	},
	sample_browser: {
		description: "Run browser sampling against logged-in AI engines (豆包/文心/Kimi/通义/元宝) via Playwright + dedicated Chrome.",
		script: "geo_sample_browser.py",
		examples: [
			"python geo_sample_browser.py --engine doubao --limit 3",
			"python geo_sample_browser.py --engine yiyan --group A",
			"python geo_sample_browser.py --engine kimi --ids A7,D5 --resume"
		],
		note: "Requires the dedicated Chrome started by 启动_调试Chrome_EN.bat (port 9222) or the script auto-launches Chrome with the saved login profile."
	},
	analyze: {
		description: "Analyze all sampling CSVs -> baseline report (mention rate / TOP3 / citation domains / competitor mentions).",
		script: "geoanalyze.py",
		examples: ["python geoanalyze.py --only 豆包,DeepSeek"]
	},
	integrate: {
		description: "Deduplicate all engine CSVs (longest answer per question) -> single 300-row CSV.",
		script: "integrate_data.py",
		examples: ["python integrate_data.py"]
	},
	report: {
		description: "Generate the HTML multi-engine comparison report.",
		script: "generate_report.py",
		examples: ["python generate_report.py"]
	}
};

/** Validate args: optional `workdir` string. Returns error message or null. */
function validateArgs(args) {
	if (args === undefined || args === null) return null;
	if (typeof args !== "object" || Array.isArray(args)) return "args must be an object";
	if (args.workdir !== undefined && typeof args.workdir !== "string") return "workdir must be a string";
	return null;
}

/** Build the plain workflow description object. */
function buildWorkflow(args) {
	const workdir = (args && typeof args.workdir === "string" && args.workdir.trim())
		? args.workdir.trim()
		: "当前工作目录（脚本所在目录）";
	return {
		ok: true,
		workflow: {
			title: "GEO 监测工作流（5 步）",
			workdir,
			steps: [
				"1. 采样准备：启动专用 Chrome（scripts/启动_调试Chrome_EN.bat）并登录目标引擎；配置 DEEPSEEK_API_KEY 环境变量（DeepSeek API 通道）",
				"2. DeepSeek API 采样：python scripts/geosample_deepseek.py [--limit N|--group X|--resume]",
				"3. 浏览器采样：python scripts/geo_sample_browser.py --engine <doubao|yiyan|tongyi|yuanbao|kimi> [--limit N|--group X|--ids A1,B2|--resume|--debug]",
				"4. 基线分析：python scripts/geoanalyze.py [--only 引擎1,引擎2]",
				"5. 整合+报告：python scripts/integrate_data.py 后 python scripts/generate_report.py 生成 HTML 报告"
			],
			scripts: WORKFLOW,
			dataFiles: {
				questions: "templates/GEO采样_问题集.csv（60 问，A-F 六组）",
				recordTemplate: "templates/GEO采样_基线记录_模板.csv（人工采样记录表）",
				outputs: "GEO采样_api快照_*.csv / GEO采样_浏览器_<引擎>_*.csv / GEO采样_基线报告_*.md / GEO采样_5引擎整合_*.csv / GEO多引擎对比报告_*.html"
			},
			keyIndicators: [
				"提及率（Mention Rate）：回答中提及 [EXPO]/[EXPO_NAME]的提问占比",
				"TOP3 推荐率：[EXPO] 进入推荐位前 3 的占比（豆包已人工回填位次）",
				"[BRAND]提及率：品牌背书信号",
				"引用域名 / 竞争实体频次：内部研判用"
			]
		}
	};
}

/**
 * Register the `geo-monitor` tool.
 * @param ctx - host plugin context (provides `tools`).
 */
function apply(ctx) {
	const definition = {
		name: "geo-monitor",
		description: "GEO（生成式引擎优化）监测工作流指引。返回完整的采样/分析/报告步骤与脚本用法（DeepSeek API + Playwright 浏览器采样豆包/文心/Kimi/通义/元宝，提及率/TOP3/引用域名分析，HTML 多引擎对比报告）。当用户要做 AI 引擎提及监测、品牌可见度基线、GEO 效果度量时使用。可选参数 workdir 指定脚本目录。",
		args: {
			type: "object",
			properties: {
				workdir: { type: "string", description: "geo-monitoring 脚本所在目录（默认取当前工作目录）" }
			},
			additionalProperties: false
		},
		handler: async (args) => {
			const error = validateArgs(args);
			if (error) return { ok: false, message: error };
			return buildWorkflow(args);
		}
	};
	ctx.tools.register(definition);
}

export { apply, name, inject };
