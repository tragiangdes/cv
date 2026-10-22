# JIZURA Auto — mp3 + lời → script After Effects dựng sẵn motion, khớp timing

Add-on cho [JIZURA](https://github.com/852wa/JIZURA). Bỏ qua bước chỉnh motion bằng tay, xuất green screen rồi
căn lại timing trong AE:

```
song.mp3 + lyrics.txt ──► Whisper căn từng chữ ──► song.lrc / song.timing.json
                                                └─► song_JIZURA.jsx ──(chạy trong AE)──► comp hoàn chỉnh + nhạc
```

- **Tự căn timing**: forced alignment (Whisper qua `stable-ts`) cho ra thời điểm bắt đầu của **từng chữ**, không chỉ từng dòng.
- **Tự tạo motion**: dùng chính engine của JIZURA (layout, hiệu ứng vào/ra, decor, camera, chuyển cảnh…). `--style auto`
  là chế độ おまかせ: chọn ngẫu nhiên style + mood theo `--seed` (cùng seed thì ra cùng kết quả).
- **Khớp đến từng cut**: JIZURA thường chia một dòng thành nhiều cut theo số ký tự. Tool vá planner để mỗi cut
  bắt đầu đúng lúc ca sĩ hát chữ đầu tiên của cut đó, và dòng chỉ ở lại trên màn hình đến khi hát xong (+ một đoạn
  ngắn), không kéo dài qua khoảng nghỉ.
- **Script AE độc lập**: một file `.jsx`, chạy bằng *File › Scripts › Run Script File…*. Script tự import nhạc,
  tạo comp đúng độ dài bài và dựng mọi layer native (text, shape, expression) — sửa tiếp được trong AE như bình thường.
  Không cần cài panel.

## Cài đặt

```bash
git clone <repo này> && cd jizura-auto
python -m venv .venv && source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt                         # có GPU NVIDIA: cài torch bản CUDA trước cho nhanh
```
Cần thêm: `ffmpeg` trong PATH, `git` (lần đầu tool tự clone JIZURA vào `jizura-auto/JIZURA`;
hoặc trỏ tới bản sẵn có bằng `--jizura đường/dẫn`).

## Dùng

```bash
python jizura_auto.py song.mp3 lyrics.txt                          # mặc định: おまかせ, seed 1, 1920×1080 24fps
python jizura_auto.py song.mp3 lyrics.txt --separate --model large-v3   # nhạc dày / giọng khó: tách vocal + model lớn
python jizura_auto.py song.mp3 lyrics.txt --style noir --seed 42 --size 1080x1920 --fps 30
python jizura_auto.py song.mp3 lyrics.txt --key green              # vẫn muốn nền green screen như workflow cũ
```
Kết quả trong `out/`: `song_JIZURA.jsx`, `song.mp3` (bản sao — script tự tìm file này cạnh nó), `song.lrc`,
`song.timing.json`. Trong After Effects: **File › Scripts › Run Script File…** → chọn `song_JIZURA.jsx`.

**Lời** (`lyrics.txt`): mỗi dòng một câu, dùng nguyên cú pháp JIZURA — `câu/ngắt` (điểm cắt thủ công),
`*nhấn mạnh*`, `câu cuối!` (flash + rung), `lời|chú thích`, `[interlude 8]`, dòng `#` là comment. Mốc LRC có sẵn
sẽ bị bỏ qua và căn lại.

**Thử nhiều phiên bản motion**: đổi `--seed` (và/hoặc `--style`) rồi chạy lại kèm `--from-timing` — không phải
căn lời lại:
```bash
python jizura_auto.py song.mp3 --from-timing out/song.timing.json --seed 7
```

**Sửa timing tay** (khi Whisper căn sai một câu): sửa `out/song.timing.json` — mỗi dòng có `s` (bắt đầu), `e` (hát xong),
`c` (thời điểm từng ký tự, không tính dấu cách) — rồi chạy lại với `--from-timing`. File `song.lrc` cũng dán thẳng
được vào JIZURA bản web hoặc panel AE gốc nếu muốn chỉnh trên giao diện đó.

### Tuỳ chọn chính

| Tuỳ chọn | Ý nghĩa |
|---|---|
| `--lang ja/en/vi/ko/zh` | ngôn ngữ lời (mặc định đoán từ chữ viết) |
| `--model small/medium/large-v3` | model Whisper; lớn hơn = chính xác hơn, chậm hơn (mặc định `medium`) |
| `--separate` | tách vocal bằng demucs trước khi căn (cần `pip install demucs`) |
| `--refine` | tinh chỉnh timestamp thêm một lượt |
| `--lead 0.12` | cho chữ xuất hiện sớm hơn giọng hát (giây) để kịp animation vào |
| `--style auto/<key>` `--mood <key>` `--seed N` | chọn look; key xem trong `JIZURA/ae/data.json` (`styleOrder`, `moodOrder`) |
| `--motion --glitch --chroma --decor --density --texture --bgswitch` | 0..1, giống các thanh trượt của panel |
| `--extra --no-wa --typo --kinetic --horror` | bật/tắt các bộ hiệu ứng như trong panel |
| `--key green/black` | nền key thay cho nền đầy đủ |
| `--light` | ít layer hơn ~40%, preview AE mượt hơn |
| `--timing-only` | chỉ xuất LRC/timing |

## Kiểm thử

```bash
python tests/test_mapping.py                                            # ánh xạ từ Whisper → từng ký tự
(cd JIZURA/dev && npm install)                                          # một lần, cho mock AE của JIZURA
node tests/ae_mock_test.js out/song_JIZURA.jsx out/song.timing.json     # dựng comp trên AE giả lập, kiểm mọi cut đúng giờ
```

## Giới hạn

- Độ chính xác phụ thuộc Whisper: đoạn rap rất nhanh, bè chồng, hoặc lời khác bản hát có thể lệch — dùng `--separate`,
  `--model large-v3`, hoặc sửa `timing.json` rồi `--from-timing`.
- Tool vá 3 điểm trong `jzMakePlan` của JIZURA (đã thử với v0.10.1). Nếu JIZURA đổi đoạn code đó, tool báo lỗi rõ ràng
  thay vì tạo script sai.
- Font: giống panel gốc — thiếu font Google nào thì AE dùng font gần giống và báo tên để cài.
