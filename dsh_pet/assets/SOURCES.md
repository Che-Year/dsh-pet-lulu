# 素材来源与许可（Assets sources & licenses）

本目录下的宠物形象素材来自两个开源项目。请在分发衍生作品时保留本说明及
各许可文件。

All pet artwork in this directory comes from the two open-source projects
below. Keep this file and the bundled license files when redistributing.

---

## lulu（水豚噜噜）— czy666chen/lulu

* 来源 Source: <https://github.com/czy666chen/lulu>
* 许可 License: **MIT**（`licenses/LICENSE.lulu`）
* 内容 Contents: `spritesheet.webp`（1536×2288，8×11 网格，Codex v2 精灵表）
  与 `pet.json`（清单：id `shuijun-lulu`，displayName「水豚噜噜」）。
* 行序布局（来自原作者 validation.json）：row0 idle、row1 running-right、
  row2 running-left、row3 waving、row4 jumping、row5 failed、row6 waiting、
  row7 running、row8 review、row9-10 十六向环视。
* 下载方式 Download:
  `git clone https://github.com/czy666chen/lulu`（或 GitHub 页面下载 zip）。

## capybara — srwang0506/HatchPet-CapybaraLulu

* 来源 Source: <https://github.com/srwang0506/HatchPet-CapybaraLulu>
* 许可 License: **Apache-2.0**（`licenses/LICENSE`），署名要求见 `licenses/NOTICE`。
* 内容 Contents:
  - `pet/spritesheet.webp`（1536×2288 动画图集，20 个 image-time 相位）
  - `pet/pet.json`（清单：id `capybara-lulu`）
  - `frames/<state>/NN.png`：9 个状态 × 20 帧的运行时相位帧
    （idle / running-right / running-left / waving / jumping / failed /
    waiting / running / review），取自该仓库 `assets/state-phases/`。
  - 动画元数据 `state-phases.json` / `idle-phases.json` 与帧标签：
    idle 相位 00 闭口静止、01 呼吸抬升、02 眨眼、03 张口、04 闭嘴。
* 下载方式 Download:
  `git clone https://github.com/srwang0506/HatchPet-CapybaraLulu`
  （原提示词中的 `srwang0506/HarchPer-Capybaralulu` 仓库已不可访问，经核实
  本仓库为同作者的同一宠物项目）。

## 使用方式（本插件内）

`dsh_pet/sprite.py` 按 `pet_type`（`lulu` / `capybara`）加载对应目录：
* `lulu`：从静态 `spritesheet.webp` 按行裁剪动画帧；
* `capybara`：优先读取 `frames/<state>/NN.png` 显式帧，动画图集作为后备。

行为 → 动作片段映射见 `sprite.py` 中的 `_build_lulu_specs` /
`_build_capybara_specs`（idle / eat / pet / jump / walk / yawn / sleep /
look）。`pet.json` 与 `spritesheet.webp` 均为原样复制，未做修改。
