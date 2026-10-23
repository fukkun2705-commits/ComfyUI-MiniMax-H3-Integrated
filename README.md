# ComfyUI-MiniMax-H3-Integrated

Integrated custom nodes for **MiniMax H3 – All-in-One Video Studio** on ComfyUI.

MiniMax H3向けの独自カスタムノードを、1つのComfyUIパッケージにまとめたリポジトリです。Scene Editor、生成方式の自動切替、最大7Clip連続生成、Part継続、音声長の補正、Face Refineの自動バイパス、Latent Upscaleの制御を提供します。

**対応生成方式：REF2VA / T2VA / I2VA / FLF2VA**

> This repository contains the author's integrated custom-node code. **Third-party custom-node source code is not included or modified.** Install the external dependencies separately.

## Installation / インストール

1. ComfyUIの `custom_nodes` フォルダで、以下を実行します。

   ```bash
   git clone https://github.com/fukkun2705-commits/ComfyUI-MiniMax-H3-Integrated.git
   ```

2. **ComfyUIが実際に使用しているPython環境**で、依存パッケージをインストールします。

   ComfyUI本体のフォルダから実行する場合：

   ```bash
   python -m pip install -r custom_nodes/ComfyUI-MiniMax-H3-Integrated/requirements.txt
   ```

   `custom_nodes` フォルダから実行する場合：

   ```bash
   python -m pip install -r ComfyUI-MiniMax-H3-Integrated/requirements.txt
   ```

3. ComfyUIを再起動します。

**重要：** 旧分割版の `ComfyUI-H3-Integrated-Scene`、`ComfyUI-H3-Integrated-ClipPart`、`ComfyUI-H3-Integrated-Audio`、`ComfyUI-H3-Integrated-Enhancement` が `custom_nodes` 内に残っている場合は、重複登録を避けるため移動または削除してください。バックアップは `custom_nodes` の外に保存してください。

Stability MatrixやPortable版では、Python実行環境が異なる場合があります。依存パッケージは必ず対象ComfyUIのPythonへインストールしてください。

## Features / 主な機能

- **H3 Scene Editor**：プロジェクトとClip単位のDuration、Prompt、参照画像・Video・Audioを管理
- **Automatic Generation Mode Switching**：REF2VA / T2VA / I2VA / FLF2VAのConditioningをプロジェクト単位で自動切替
- **Up to 7 Clips**：最大7Clipの連続生成、Duration Planning、Clip間Audio Alignment
- **Part NEW / CONTINUE**：Part継続用の制御、MP4 TailとNative AV Latentを利用したMotion Context連携
- **Native AV Latent Slot Management**：`Current Part Slot` に応じて、前Partの固定番号ファイルを読み込み、現在Partの固定番号ファイルへ保存
- **FaceAutoBypass**：顔が検出されない場合にFace Refineをスキップするための制御
- **Latent Upscale / Pass2 Controls**：Latent UpscaleとPass2 Refineの共通設定
- **Audio Tools**：Audio Conform、Pre-trim Audio Grid、Audio Alignment関連の補助処理

### Scene Settings Refresh & Validation

`scene_settings` の更新により、Scene Editorで保存した `scenes.json` の変更をComfyUI実行時に読み直す構成になっています。

- Durationだけでなく、Prompt、参照画像、Video、AudioなどのScene設定を読み込み直す
- 読み込み途中でScene設定ファイルや参照素材が変更された場合、エラーとして処理を停止する安全対策を追加
- Scene Editorで**未保存の変更**は検出できないため、生成前に必ず「全Clipを保存」してください

**注意：** この対策は設定の更新漏れ・読み込み競合のリスクを減らすためのものです。すべての更新タイミングや実行中の変更に対して完全な一致を保証するものではありません。また、参照Video・Audioなどを含むSceneは、再読み込みに時間がかかる場合があります。

### FLF2VA Pass2 Auto Warp Guard

`mode_router` に、FLF2VAのPass2 Conditioningを自動調整する対策を追加しました。

- **Pass1**：FLF2VA Conditioningを維持
- **Pass2**：FLF2VA選択時にT2VA Conditioningへ自動切替し、終端付近の横方向の伸び・歪みを抑制
- **他の生成方式**：REF2VA / T2VA / I2VAには、このFLF2VA専用の切替を適用しない
- 手動でPass2の配線を変更する必要はありません

※ 特定条件で確認された映像歪みへの対策であり、あらゆる素材で歪みが発生しないことを保証するものではありません。

## H3 Scene Editor / 操作の概要

ComfyUIを起動して、次のURLを開きます。

```text
http://127.0.0.1:8188/h3-scene-editor
```

※ ComfyUIの使用ポートが8188以外の場合は変更してください。

1. Scene Editorで新規Projectを作成します（例：`Project01`）。
2. Editor上部の **Scene Loaderに設定するパス**（例：`H3_Scene_Projects/Project01/scenes.json`）をコピーします。
3. ワークフローの `SCENE PROJECT JSON PATH — Edit Here` に貼り付けます。
4. 各ClipのDuration・Prompt・参照素材を設定し、**「全Clipを保存」**をクリックします。
5. `Use Clip Total` と `Total Part Duration Out` を確認し、生成を実行します。

生成方式はプロジェクト単位で共通です。同一Part内で異なる生成方式を混在させる構成ではありません。

## Part Continuation / Part継続

- **Part1**：`PART MODE = Part1 NEW`、`Current Part Slot = 1`
- **Part2**：`PART MODE = Part2+ CONTINUE`、`Current Part Slot = 2`。前PartのMP4を指定
- **Part3以降**：`PART MODE = Part2+ CONTINUE`、`Current Part Slot = 今回のPart番号`。対応する前PartのMP4を指定
- `Use Clip Total` は各Partで実際に生成するClip数（1〜7）です。`Current Part Slot` と混同しないでください
- MP4 Tailの `tail_frames` は通常 **22** のまま使用します

Native AV Latentの固定番号例：

```text
ComfyUI/output/h3_part_context/integrated_parts/
  last_clip_00001.safetensors  # Part1
  last_clip_00002.safetensors  # Part2
  last_clip_00003.safetensors  # Part3
```

CONTINUEでは、**前PartのMP4と、それに対応する同じ生成回のAV Latent** を使用してください。同じPart番号を再生成すると、保存済みLatentが上書きされる場合があります。異なるProjectも同じ固定番号フォルダを使用するため、並行作業ではバックアップと管理に注意してください。

**Part出力の違い：** REF2VA / T2VA / I2VAは各Partの個別MP4を出力します。FLF2VAはPart2以降で前Partまでを含む**累積MP4**を出力する実験的な結合機能を使用します。FLF2VAの累積MP4同士を再結合しないでください。

## External Workflow Dependencies / 外部カスタムノード

このリポジトリ**単体ではワークフローの全ノードは揃いません**。下記はワークフロー側で使用する外部パッケージです。各リポジトリのライセンスと導入方法を確認して、別途インストールしてください。

- [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) — Set/Get、Attention関連など
- [ComfyUI-H3-Motion-Context-MultiRef](https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef) — Motion Context
- [ComfyUI-H3-FaceRefine](https://github.com/Carasibana/ComfyUI-H3-FaceRefine) — 顔補正本体
- [Comfyui_Minimax_h3_latent_Upscaler](https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler) — 3D Latent Upscale
- [ComfyUI-H3-AudioRefine](https://github.com/Adudeguyman/ComfyUI-H3-AudioRefine) — Audio Refine
- [ComfyUI_Nvidia_VFX_Nodes](https://github.com/Comfy-Org/ComfyUI_Nvidia_VFX_Nodes) — RTX Video Super Resolution（使用時。対応するNVIDIA RTX GPUとCUDA/PyTorch環境が必要）

FaceAutoBypassの制御は本統合パッケージに含まれていますが、Face Refine本体は外部パッケージが必要です。モデルファイルもこのリポジトリには含まれていません。

## Validation / 検証状況

- 本統合ワークフローでは、REF2VA / T2VA / I2VA / FLF2VA、複数Clip、Part継続などの実機検証を実施しています。
- FLF2VA Pass2 Auto Warp Guardは、1Clipおよび4Clipの実機検証で終端の横伸び対策として正常動作を確認しています。
- Scene Settingsの更新・安全対策については、Project切替、Duration変更、参照Audio・Videoを伴う読み込みで正常動作を確認しています。
- 以前不定期に発生したScene設定の更新不良については、継続的な運用で再発有無を確認中です。すべての環境・条件での動作を保証するものではありません。

## Related Workflow / 対応ワークフロー

[MiniMax H3 – All-in-One Video Studio](https://github.com/fukkun2705-commits/MiniMax-H3-All-in-One-Video-Studio)

ワークフローJSON、詳しいモデル配置、Scene Editor・Part継続の操作手順は上記リポジトリとワークフロー内Noteを参照してください。

## License

MIT License. See [LICENSE](LICENSE).

This repository provides the author's integrated code only. Third-party projects retain their own licenses and are installed separately.
