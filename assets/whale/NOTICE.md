# 鲸鱼娘立绘 · 来源与许可

`mascot.png` 是 `DSniang1.png` 的派生文件：裁边 → 灰化 → 锐化 → 16 级 Floyd–Steinberg 抖动，
由 [`tools/make_mascot.py`](../../tools/make_mascot.py) 生成。

| 项 | 说明 |
|---|---|
| 原始文件 | `DSniang1.png`，来自 [dsh-whale-widget](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget) v0.4.2 的 `assets/` |
| 原作者 | MeteorNOX |
| 上游说明 | 按该项目的 `PROVENANCE.md`，**`assets/` 下的美术素材不在 MIT 覆盖范围内**，"原样提供、仅用于运行本插件、不授予再许可"；该图据其说明为 AI 工具生成、原始出处不可考 |
| 本仓库用途 | 仅用于个人看板显示，**同样不授予再许可**，也不声明为本仓库原创 |

**因此：本文件不受本仓库 MIT LICENSE 覆盖。** 如果你要再分发、商用或公开部署，请自行确认权利状态，
或直接删除 `mascot.png` —— 渲染器在缺图时会自动退化成纯数字面板，不会报错：

```bash
rm assets/whale/mascot.png        # 或 git rm
python tools/make_mascot.py       # 本地有插件时重新生成
```

权利人如认为此文件不当，开 issue 说明即可，会立即移除。
