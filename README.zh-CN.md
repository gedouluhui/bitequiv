# BitEquiv：把整数优化变成可检查的命题

[直接查看在线示例](https://gedouluhui.github.io/bitequiv/example-report.html) · [发行版下载](https://github.com/gedouluhui/bitequiv/releases)

比较两个固定位宽的无符号整数表达式。Z3 负责求解；独立的 Python 整数解释器重放反例；离线 HTML 报告展示具体输入、逐步结果与发生差异的比特。

不是新求解器，也不替代完整 C / LLVM 程序验证。它适合讲解、检查和回归测试小型位运算改写，不证明性能、常数时间或模型质量。

## 快速开始

需要 Python 3.11+。在源码目录创建并激活虚拟环境，然后：

```bash
python -m pip install .
python -m bitequiv check examples/overflow-mean.json --json result.json --html result.html
```

这条示例命令应返回退出码 **1**，表示发现反例，不是工具崩溃。双击 `result.html` 即可查看，不需要网络。再次运行请换输出文件名，已有文件不会被覆盖。目前不宣称已发布到 PyPI。

8 位整数中，`(x+y)>>1` 与 `(x&y)+((x^y)>>1)` 看似都是求平均，但 x=y=128 时前者先溢出，得到 0，后者得到 128。限制 x、y 都不超过 127 后，两式才在该范围内等价。工具给出的具体反例不保证是最小反例，也可能与这个手算例子不同。

```bash
python -m bitequiv check examples/bounded-mean.json
python -m bitequiv check examples/lost-high-bit.json
```

## 0.2 源码的新证据工作流

0.2.0新增两个不依赖求解器的命令；0.1.0发行资产保持不变，请下载最新发行版或从当前源码安装。

```bash
bitequiv export examples/overflow-mean.json --smt2 question.smt2
bitequiv replay docs/example-report.json
```

`export` 不调用求解器，导出包括完整取值范围的标准QF_BV问题。退出0仅代表文件创建成功；将文件交给独立安装的Z3/cvc5后，sat表示可能不等价、unsat表示声明范围内等价、unknown表示未得结论。导出文件不包含求解器专用预算，外部运行需按该求解器说明设置限制。

`replay` 不信任报告写的“通过”，而是从输入重新计算反例：核对指纹、语义、输入域、两个结果、每步数值和二进制、不同bit。完整重算匹配才返回 `verified_counterexample` / 退出0；被篡改为 `mismatch` / 退出1；“等价”或“未知”等不能凭具体反例复验的报告返回 `unverifiable` / 退出2；格式/文件错误退出3。

这两个命令不用Z3也能工作；普通安装仍带Z3以支持`check`。报告复验只能验证其中问题上的具体数学反例，不认证作者、历史求解过程或元数据，更不等于验证所有输入。

## 必须读懂的边界

- 位宽为 1–64，最多 8 个变量。每一步都按该位宽回绕；不是 Python 任意精度整数，也不是 C 的整数提升规则。
- `>>` 是逻辑右移；移位量也是同宽位向量，值大于等于位宽时结果为 0。这不是 C 越界移位规则。
- 支持 `+ - * & | ^ << >>`、一元 `+ - ~` 与括号，不支持函数、导入、除法、比较、浮点或任意代码执行。
- 只允许非空、无符号、包含两端的变量范围。超时／资源不足返回未知，绝不等同于通过。
- 输出包括表达式与反例值；私有代码的报告不要直接公开。

退出码：0＝在声明范围内等价；1＝找到并重放反例；2＝未知；3＝输入、参数或文件操作出错。

## 验证与贡献

```bash
python -m unittest discover -s tests -v
python scripts/check_mutations.py
python -m pip install ".[crosscheck]"
python scripts/check_cross_solver.py
```

测试覆盖手算边界、小位宽逐算子穷举、求解结论与枚举对照、反例重放分歧、真实 CLI 与文件保护。变异测试只改临时副本，不修改产品源码。报告没有独立证明证书；等价结论仍信任 Z3 和表达式转换。

跨求解器检查把独立导出的SMT问题交给Z3和cvc5，与原Z3 API路径比较，并重放SAT赋值。缺少cvc5、超时、unknown和不一致均使该检查失败，不能当作跳过后通过；有限语料上的一致仍不是独立证明证书。

请提交可公开的最小反例及位宽、输入范围，不提交账号、私有源码或数据。详细语义见 [DESIGN.md](docs/DESIGN.md)，英文使用说明见 [README.md](README.md)。MIT 许可；项目由 AI 辅助实现。

## 快速开始与支持状态

### 问题
为两个小型固定宽度无符号整数表达式的等价性寻找具体反例，并独立重放证据。

### 安装
```sh
python -m pip install .
```

### 成功命令
```sh
python -m bitequiv check examples/bounded-mean.json
```
预期：Z3 在受限非空域上证明表达式等价；退出码 0。

### 故意失败命令
```sh
python -m bitequiv check examples/overflow-mean.json --json result.json --html result.html
```
预期：找到满足赋值并独立重放，命令退出码 1。

### 证据与覆盖边界
证据包括手算回绕/移位用例、宽度 1-4 的穷举算子表、小型域求解器/枚举器对比、真实资源限制 unknown、witness 不一致对照、子进程往返、可选跨求解器检查和报告重放。求解器证明不是关于生成表达式的程序的证明，也不输出证明证书。

### 支持状态
版本 0.2.0 是面向 Python 3.11+ 和 z3-solver>=4.12,<5 的 alpha。文档通过 GitHub Release 提供源码和 wheel 安装，不是 PyPI。维护为尽力而为，不提供 SLA。

### 限制
语言是 1-64 位单一无符号宽度，具有显式算子和范围；不是 C/LLVM 语义。不提供自动 LLVM 提取、最小 witness 保证、常量时间/安全声明或独立可检查的证明证书。
