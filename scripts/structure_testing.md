# 主干与高亮测试

## 无网络回归

```powershell
.venv/Scripts/python.exe scripts/test_structure_cases.py
.venv/Scripts/python.exe scripts/test_structure_markup.py
.venv/Scripts/python.exe scripts/test_structure_stream.py
node scripts/test_structure_focus.cjs
```

当前套件包含 21 类句子、64 项基础检查、10 项唯一对齐修复和安全拒绝检查，另有多留修饰与强调句/形式主语对照断言。
覆盖形式主语/宾语、宾补、并列省略、倒装、only 限制、强调句、定语从句、让步从句、
被动情态否定、名词性从句、短语动词、not until、there be，以及大小写、重复词歧义、
UTF-16、错误词形和连字符边界。

## DeepSeek 实测（会消耗余额）

```powershell
.venv/Scripts/python.exe -X utf8 scripts/test_structure_cases.py --live --repeat 2
# 只重跑指定类型
.venv/Scripts/python.exe -X utf8 scripts/test_structure_cases.py --live --case ellipsis --case story
```

使用项目配置的模型和生产提示词、解析器；两路并发，单次超时 60 秒，不自动重试。
只发送套件例句，不读取文章、用户或历史记录，不写学习数据。
结果保存到被 Git 忽略的 tmp/；不记录密钥，异常只记录类型。

## 判定边界

- `valid_core`：主干与原文成功定位，不代表语法分析正确。
- `required_missing` / `unwanted_present`：各用例指定的关键成分与不应保留的内容。
- `restoration_present`：需要简化表达的用例是否输出明确标为非原文的辅助段落。
- `passed`：定位、关键成分、不得多留的内容和简化表达检查全部通过，不是通用语法正确率。

2026-10-20：初次 16 句有 13 句通过；改进提示词后仍有片段拼接、大小写等定位失败。
加入唯一顺序对齐兜底后连续两轮 32/32 通过定位和关键成分检查。
人工检查仍发现主干偏长、强调框架保留的问题；此数据不能推导出任意句子都正确。
上述 32/32 是旧版宽松检查结果，不能当作当前更严格规则的通过率。
新增简化表达后首轮实测：2 句成功，19 句 APIConnectionError，尚未完成全套真实模型验证。

## 简化表达边界

仅在右侧解释中使用“◆ 简化表达（辅助改写，非原文）”，复杂成分可概括，倒装可还原。
原文骨架、定位数据与该段落分离；左侧不替换文字，不加入折叠替换交互。
简单句不强制生成简化段落。`test_structure_markup.py` 验证改写词不能污染原文定位。

## 分层回答展示

结构任务单独允许空行及少量 **加粗**；词汇等其他回答维持原有规则。
前端只用文本节点和 strong 渲染，不解析 HTML、链接或任意 Markdown。
标题、英文/中文分行和 ↳/↳↳ 两级缩进仅作用于问答区；复制保留原始换行。
复杂从句先给内部主干，再按意思拆解嵌套动作；避免重复“主干串起来”。

```powershell
node scripts/test_structure_presentation.cjs
.venv/Scripts/python.exe scripts/test_structure_presentation.py
# 实测8句（包括 social cure 原句）；连续两次连接失败停止
.venv/Scripts/python.exe -X utf8 scripts/test_structure_presentation.py --live
```

报告：tmp/structure-presentation-report.json，保存完整回答和定位，供人工检查语义。
自动断言覆盖模板、分段和层次标记，不等同于全文语法/翻译质量评审。

## 主干精简专项

```powershell
.venv/Scripts/python.exe scripts/test_structure_concision.py
.venv/Scripts/python.exe -X utf8 scripts/test_structure_concision.py --live
```

逐一检查回答首行和实际高亮：不允许把方式说明/附属从句混入整句主干，
同时保护必要介词搭配、地点补语、状态补足语、名词性主语和否定限制。
2026-10-21 最终规则实测 8 句各两次，15/16 通过严格断言。
social cure 原句两次均为 But Tina Rosenberg contends that peer pressure can also be a positive force.
仍有一次多保留普通修饰 heavy，测试仍计为失败，不放宽判定以掩盖波动。
原始报告：tmp/structure-concision-report.json。并非通用语法正确率或所有输入的保证。

兜底只在模型定位失败时使用：去掉方括号补词，将主干词按原文顺序对齐。
仅接受唯一完整路径，不猜重复词位置，不做词形恢复，不匹配连字符词的一部分。
如果主干自身漏词且模型高亮也漏同一个词，一致性检查无法检测，仍需语义用例和人工审查。

## 正式系统分层交互

```powershell
.venv/Scripts/python.exe scripts/test_structure_reveal.py
node scripts/test_structure_reveal.cjs
.venv/Scripts/python.exe scripts/test_structure_stream.py
# 调用真实模型，历史隔离；报告 tmp/structure-reveal-production.json
.venv/Scripts/python.exe -X utf8 scripts/test_structure_reveal_live.py
# 需要可用的 playwright 与 Edge；端口8001服务运行中
node scripts/test_structure_reveal_browser.cjs
node scripts/test_structure_reveal_browser.cjs --live-result
```

浏览器测试使用隔离上下文和模拟 SSE，不登录真实账号、不写学习记录。
--live-result 回放生产调用的真实返回，验证正式首页脚本的回答渲染、点击解锁、级联收回、
指代高亮、独立背景、字号与原文不变、暗色、窄屏以及切换文章后清理。
真实生产调用已验证 social cure 原句返回五个节点及正确依赖链。
接口降级测试确认无效依赖图不会破坏正文或主干；不是所有句子的模型语义质量保证。
