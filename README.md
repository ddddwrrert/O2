# O2

独立可运行的搜索环：**Drive → Certify → Lease → Return**。

用来治「固定 `select → mutate → evaluate → survive` 中途假活」：官方分已经不动，评测预算还在烧在当前全局最优父本的小改上。`select` / `mutate` / `survive` 的实现全程不换；中途只发放、收回一份会到期的**父本租约**。

本仓库不依赖 Organon 或其他项目。

## 公民：租约

同一时刻最多一份 `open` 租约：

| 字段 | 含义 |
|------|------|
| `parent_id` | 非现任全局最优的档案程序 |
| `view` | 现任被档案压过、且缺口最大的官方种子子集 |
| `budget_left` | 剩余官方评测次数 |
| `status` | `open` / `returned` / `expired` |

## 发放条件（修订版）

暖机结束后，**同时**满足：

1. **停分**：最近 `W` 次评测，全局最优严格未提高  
2. **塌缩**：最近 `M` 次提案中，父本等于现任的比例 ≥ `ρ`（默认 0.75）

然后：

- 对每个种子算 `δ_s = max_{P≠I} score_P(s) - score_I(s)`  
- `view` = 正缺口最大的前 `k` 个种子；若为空 → `empty_gap` 拒发  
- `parent` = 在 `view` 上聚合最高、且优于现任至少 `γ`；否则 `no_margin`  
- `(parent, hash(view))` 已关闭过 → `no_renew`  
- 配额 `min(K, ⌊0.1·B_rem⌋, 2+|view|)`，小于 2 → `budget_too_small`

拒发时**不**退回随机父本。

## 主环

```text
Drive:   select → mutate → evaluate → survive
Certify: 停分 ∧ 塌缩 → try_issue_lease
Lease:   固定父本；可选口头方向表；完整 V；视图内名次 + 补集不回退才入档
Return:  配额用尽或视图连平 → 关闭并写入不可续约表
```

## 安装与运行

需要 Python ≥ 3.10。无第三方运行时依赖。

```bash
cd O2
python -m pip install -e ".[dev]"
python -m o2 --B 80 --seed 0 --out runs/lease-s0
python -m o2 --mode drive --B 80 --seed 0 --out runs/drive-s0
python -m pytest -q
```

Windows PowerShell 同样可用：

```powershell
python -m pip install -e ".[dev]"
python -m o2 --B 80 --seed 0 --out runs/lease-s0
python -m pytest -q
```

## 输出

`--out` 目录写入：

- `summary.json` — 终局最优、证书次数、发放/拒发/关闭统计  
- `config.json` — 本次配置  
- `events.jsonl` — 逐步 Drive / Issue / Lease / Return 事件（lease 模式）

## 对照

| 模式 | 含义 |
|------|------|
| `--mode lease` | 完整 O2 |
| `--mode drive` | 永不发放租约（把 `ρ` 抬到不可能） |
| `--no-verbalized` | 租约步不列口头方向，直接按 view 扰动 |

## 设计边界

- 评测器与三个算子函数身份在关闭前后不变（哈希写入 summary）  
- Mock 任务是多多种子向量峰，用来在本地复现「易种子父本垄断」；换成真实 AHC judge 时只替换 `o2/task.py` 的评分接口  
- 本仓库不包含训练、不热换搜法实现、不并行多租约
