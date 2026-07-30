# 茄子桌宠 · Codex V1 精灵表重绘规范

依据 [awesome-codex-pet](https://github.com/legeling/awesome-codex-pet) V1 合同编写，用于重新生成无裁切、可等分切帧的 `spritesheet`。

## 1. 图集几何（必须遵守）

| 项 | 值 |
| --- | --- |
| 整图尺寸 | **1536 × 1872** |
| 网格 | **8 列 × 9 行** |
| 单格 | **192 × 208**（宽 × 高） |
| 未用格 | **全透明**（或纯色键后必须抠净） |
| 导出 | PNG（本项目可用）或 `spritesheet.webp`（Codex 投稿） |

切帧公式（等分，无需谷值检测）：

```text
frame(row, col) = image[row*208 : (row+1)*208,  col*192 : (col+1)*192]
```

**安全区（强烈建议）**

- 角色主体落在格内约 **160×176** 的中心区
- 四周至少留 **12–16 px** 透明边，气球/怒气标/手持物不得贴边或出格
- 所有行统一**脚底基线**（约距格底 16–24 px），避免播放时上下跳

## 2. 角色身份锁定（所有行共用）

**主体**：圆润紫色茄子；绿色多瓣蒂/叶子帽；可爱简单五官（黑豆眼、粉腮红、小嘴）；短粗手臂与小脚。

| 风格 | 视觉关键词 |
| --- | --- |
| **毛绒实拍 (plush)** | needle-felt / wool plush，毛毡纹理，柔和阴影，手工感 |
| **矢量扁平 (vector)** | clean thick black outline，flat fill，轻微体积高光，贴纸感 |

**全局禁止**（Codex 同款）

- 不要：速度线、烟尘、地面长阴影、对话框、文字、UI、棋盘格、风景背景
- 不要：半透明光晕、拖影、模糊运动
- 背景：单格内用**纯色色键**（推荐 `#00FF00` 绿幕；若角色含绿色蒂，改用 **品红幕 `#FF00FF`**）
- 效果物（泪、小蒸汽）必须**贴着角色**、硬边、同格内，且不得像独立精灵漂在远处

## 3. 九行动作规划（映射现有茄子主题）

现有表大致是：桌前 / 气球×2 / 互动猫 / 害羞 / 奔跑瓶 / 打字 / 崩溃 / 瘫坐。  
按 Codex 固定顺序重排如下（点击循环可按行号 0→8）：

| 行 | Codex 名 | 帧数（建议） | 茄子主题落地 | 制作要点 |
| --- | --- | ---: | --- | --- |
| 0 | `idle` 待机 | 6 | 桌前轻呼吸（可保留小木桌+显示器，或纯站立） | 眨眼/重心微移；道具不挡脸；基线稳 |
| 1 | `running-right` 右跑 | 8 | 持粉瓶兴奋小跑（向右） | 明确朝右；步态交替；**无**速度线/烟尘 |
| 2 | `running-left` 左跑 | 8 | 同上镜像语义（向左） | 非对称道具勿直接翻面出错则单独画 |
| 3 | `waving` 挥手 | 6 | 举手打招呼 / 偷看挥手 | 用手/短臂招呼；无悬空波浪线 |
| 4 | `jumping` 跳跃 | 6 | 起跳→腾空→落地（可带气球但**整格容纳**） | 气球必须完整；落脚点与比例稳定 |
| 5 | `failed` 失败 | 6 | 害羞捂脸 / 沮丧瘪嘴 | 表情为主；附加效果贴身 |
| 6 | `waiting` 等待 | 6 | 看手机 / 气球闲逛等待 | 像「等回复」；区别于 idle |
| 7 | `running` 忙碌跑 | 8 | 生气冲刺持瓶（表示忙碌） | 不同于左右跑的「工作中」感；可微前倾 |
| 8 | `review` 审查 | 6 | 桌前打字/盯屏幕认真检查 | 视线与前倾；勿加无关道具 |

> 猫互动：可并入 `waving` 前 2–3 帧（茄子旁小橙猫），或只在 `idle` 偶发；不要单独占满一行导致缺 Codex 动作。

## 4. 逐行生成提示词（英文，便于 imagegen）

生成方式建议：**一次一行条带**（宽 1536、高 208），或一次一格再由脚本拼 atlas。  
每行提示前都加上「角色锁定」+「风格」+「品红幕背景」前缀。

### 共用前缀

```text
Digital desktop-pet sprite strip. One eggplant character only (unless noted).
Character lock: round purple eggplant body, green leafy calyx hat, simple cute face
(black bead eyes, pink blush, tiny mouth), stubby arms and feet. Consistent proportions
across frames. Style: {PLUSH|VECTOR}. Flat pure magenta background #FF00FF, no gradient,
no shadow on ground, no scenery. Each frame fits inside a 192x208 cell with 16px safe margin;
nothing clipped. No text, UI, speed lines, dust, speech bubbles. Hard opaque edges.
```

`{PLUSH}` → `needle-felt wool plush texture, soft handmade look`  
`{VECTOR}` → `clean thick black outlines, flat cel shading, sticker style`

### Row 0 — idle（6 帧，用前 6 格；后 2 格留空透明）

```text
Row idle: 6-frame loop of the eggplant sitting at a tiny wooden desk with a small black monitor,
gentle breathing and occasional blink, calm happy face. Same desk scale every frame.
Loopable. Empty cells 7-8 unused.
```

### Row 1 — running-right（8 帧）

```text
Row running-right: 8-frame walk/run cycle facing RIGHT. Eggplant holds a small pink bottle.
Clear left-right foot alternation, slight body bounce. No motion lines, no dust clouds.
```

### Row 2 — running-left（8 帧）

```text
Row running-left: 8-frame walk/run cycle facing LEFT. Same pink bottle in the correct hand
for leftward motion (do not mirror readable details incorrectly). No motion lines, no dust.
```

### Row 3 — waving（6 帧）

```text
Row waving: 6-frame greeting. Eggplant raises a stubby arm to wave at viewer, cheerful smile.
Optional: frames 1-2 include a tiny orange felt cat sitting beside it (same style), then cat
optional leave; wave continues. No floating wave marks.
```

### Row 4 — jumping（6 帧）

```text
Row jumping: 6 frames — crouch, launch, apex in air, fall, land squash, recover.
OPTIONAL cream moon balloon on a short string fully inside the 192x208 cell with margin;
balloon top must not touch cell border. Stable silhouette size.
```

### Row 5 — failed（6 帧）

```text
Row failed: 6-frame shy/embarrassed loop. Hands near face, closed or watery eyes, pink blush
stronger. Small attached sweat drop OK if hard-edged and touching the body. No detached icons.
```

### Row 6 — waiting（6 帧）

```text
Row waiting: 6-frame waiting loop. Eggplant holds a grey phone, glances at it, slight sway,
patient expression. Feels like waiting for a reply, not idle desk work.
```

### Row 7 — running / busy（8 帧）

```text
Row busy-run: 8-frame energetic charge facing slightly right, angry brows, open mouth,
pink bottle in hand. Tiny hard-edged anger puffs attached near head (inside cell margin).
This means "working hard / busy", not directional travel. No speed lines.
```

### Row 8 — review（6 帧）

```text
Row review: 6-frame focused check at desk with laptop or monitor. Furrowed or attentive brows,
leaning forward, typing or staring at screen. Serious review mood, not sleepy.
```

## 5. 验收清单（生成后必查）

1. 整图正好 **1536×1872**，可按 192×208 整齐切开。  
2. 九行语义符合上表；播放 GIF 无基线跳动、无左右跑方向反了。  
3. 气球/怒气/瓶子完整进格，无邻行渗色。  
4. 棋盘格 / 深底 / 浅底均无绿边、紫边、色键残留。  
5. 未用格全透明。  
6. 毛绒与矢量各出一套，文件建议：
   - `eggplant-spritesheet-plush-v1.png`
   - `eggplant-spritesheet-vector-v1.png`

## 6. 接入本项目（生成完成后）

`appearance.py` 可改为**等分网格**（不再做谷值分行）：

```python
CELL_W, CELL_H = 192, 208
COLS, ROWS = 8, 9
# rect = QRect(col * CELL_W, row * CELL_H, CELL_W, CELL_H)
```

`_FALLBACK_FRAME_COUNTS` 建议与上表一致：`[6, 8, 8, 6, 6, 6, 6, 8, 6]`（每行实际有内容的格数；其余透明格跳过）。

## 7. 推荐制作流程

1. 锁定一张「正面设定图」作参考（毛绒 / 矢量各一张）。  
2. 按行调用 imagegen（带 layout guide：8 个 192 宽竖槽更好）。  
3. 脚本：抠色键 → 校验每格 bbox 在安全区内 → 拼成 1536×1872。  
4. 用本仓库预览：替换 rgba 文件名并跑桌宠点击循环。  
5. （可选）按 Codex 打包 `pet.json` + `spritesheet.webp` 投稿。

---

**结论**：当前裁切问题来自「非标准紧凑打包」；按本规范重绘后，行距与格高固定，气球等道具只要画进 192×208 安全区就不会再被截断。
