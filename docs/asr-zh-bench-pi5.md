# 树莓派 5：中文 ASR 基准（20 段）

日期：2026-07-31  
硬件：Raspberry Pi 5 Model B（8GB，aarch64）  
语料：Piper `zh_CN-huayan-medium` 合成，20 句日常指令/健康相关中文  
平均音频时长：约 **3.09s**（2.27–4.44s）

## 对比模型

| 引擎 | 运行时 | 备注 |
|------|--------|------|
| SenseVoice-Small INT8 | sherpa-onnx | 4 threads，`use_itn=True` |
| Zipformer-CTC-zh INT8 | sherpa-onnx | 4 threads |
| Whisper tiny / base / small | whisper.cpp | `-l zh -t 4 -np -nt` |

每模型先 warmup 1 次，再逐句计时。

## 主指标：耗时

| 模型 | 平均耗时 | 中位 | 最小 | 最大 | 平均 RTF |
|------|----------|------|------|------|----------|
| SenseVoice-Small INT8 | **0.141s** | 0.133s | 0.110s | 0.195s | **0.046** |
| Zipformer-CTC-zh INT8 | **0.318s** | 0.257s | 0.203s | 0.695s | **0.101** |
| Whisper tiny | 1.090s | 1.075s | 0.913s | 1.599s | 0.364 |
| Whisper base | 2.618s | 2.503s | 2.192s | 3.534s | 0.879 |
| Whisper small | 9.970s | 9.833s | 9.311s | 11.121s | 3.365 |

相对 SenseVoice：

- Zipformer 约慢 **2.3×**
- Whisper tiny / base / small 约慢 **8× / 19× / 71×**

## 参考：CER

| 模型 | 平均 CER |
|------|----------|
| Zipformer-CTC-zh INT8 | **3.79%** |
| SenseVoice-Small INT8 | **3.90%** |
| Whisper small | 19.66% |
| Whisper base | 26.03% |
| Whisper tiny | 32.41% |

说明：

- 本机 CER 用于粗看稳定性，不是公开数据集正式评测。
- Whisper 常输出繁体字（如「現在」「客廳」），按简繁不同字计错，CER 会偏高。
- SenseVoice 与 Zipformer 更可比：两者平均 CER 都约 **4%**。

## 结论（中文、Pi 5）

- **耗时首选**：SenseVoice-Small INT8（约 0.14s / 句，RTF ≈ 0.05）。
- **精度接近、仍很快**：Zipformer-CTC-zh INT8（约 0.32s / 句）。
- **Whisper**：小模型中文合成音上慢且不稳定；对话音箱本地中文 STT 不建议作为主路径。

## 语料（20 句）

| # | 文本 |
|---|------|
| 00 | 早上好，今天我吃了两个鸡蛋和一杯牛奶。 |
| 01 | 请帮我记录一下，午餐是一碗米饭和一份青菜。 |
| 02 | 我今天还剩多少卡路里可以吃？ |
| 03 | 现在几点了，提醒我晚上九点喝水。 |
| 04 | 把客厅的小夜灯打开。 |
| 05 | 今天天气怎么样，需要带伞吗？ |
| 06 | 播放我最喜欢的中文歌曲。 |
| 07 | 小爱同学，停止播放音乐。 |
| 08 | 帮我查一下明天的日程安排。 |
| 09 | 晚餐我想吃西兰花和鸡胸肉，热量高不高？ |
| 10 | 我已经走了一万步，今日运动量够不够？ |
| 11 | 请把温度调到二十四度。 |
| 12 | 帮我给 Timmy 发一条消息，说我晚上回家吃饭。 |
| 13 | 现在有什么新闻，简单说一下。 |
| 14 | 提醒我明天早上八点起床跑步。 |
| 15 | 今天的血糖记录了吗，帮我查一下趋势。 |
| 16 | 把卧室的空调关掉，谢谢。 |
| 17 | 我想听一个睡前故事。 |
| 18 | 苹果和香蕉哪个含糖量更高？ |
| 19 | 再见，祝你晚安，做个好梦。 |

## 典型错误（SenseVoice / Zipformer）

| 参考 | SenseVoice | Zipformer |
|------|------------|-----------|
| 帮我给 Timmy 发一条消息… | 丁妮 | 丁妮 |
| 西兰花和鸡胸肉 | 西兰话 / 何计胸肉 | 西兰话 / 合计胸肉 |
| 苹果和香蕉 | 橡蕉 | 橡胶 |
| …查一下趋势 | 去试 | 去世 |

英文专名、相近音专有名词仍是薄弱点；日常短指令多数可正确识别。

## 产物路径（Pi）

| 内容 | 路径 |
|------|------|
| 语料 WAV + refs | `~/voice-bench/results/corpus_zh/` |
| 原始结果 JSON | `~/sherpa-onnx/results/asr_zh_20_20260731_192900.json` |
| 基准脚本 | `~/sherpa-onnx/scripts/zh_corpus_bench.py` |
| 运行日志 | `~/sherpa-onnx/logs/zh_corpus_bench.log` |

复跑：

```bash
source ~/sherpa-onnx/venv/bin/activate
python ~/sherpa-onnx/scripts/zh_corpus_bench.py
```
