# BitEquiv：把整数优化变成可检查的命题

[直接查看在线示例](https://gedouluhui.github.io/bitequiv/example-report.html) · [下载 v0.1.0](https://github.com/gedouluhui/bitequiv/releases/tag/v0.1.0)

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
```

测试覆盖手算边界、小位宽逐算子穷举、求解结论与枚举对照、反例重放分歧、真实 CLI 与文件保护。变异测试只改临时副本，不修改产品源码。报告没有独立证明证书；等价结论仍信任 Z3 和表达式转换。

请提交可公开的最小反例及位宽、输入范围，不提交账号、私有源码或数据。详细语义见 [DESIGN.md](docs/DESIGN.md)，英文使用说明见 [README.md](README.md)。MIT 许可；项目由 AI 辅助实现。
