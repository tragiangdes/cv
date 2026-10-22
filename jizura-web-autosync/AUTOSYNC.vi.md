# JIZURA + Tự căn lời (AI) + Xuất script AE

Bản JIZURA này thêm 2 nút vào khung **Âm thanh và thời gian**:

| Nút | Làm gì |
|---|---|
| **✦ Tự căn lời (AI)** | Nghe bài hát (Whisper chạy ngay trong trình duyệt, nhạc không bị tải lên mạng), đặt điểm bắt đầu của **từng câu và từng cảnh** đúng vào giọng hát. Câu chỉ ở lại màn hình đến khi hát xong. Timing vẫn giữ khi bấm "Sắp xếp ngẫu nhiên" / đổi phong cách. |
| **Xuất script AE (.jsx)** | Tạo 1 file `.jsx` chạy được không cần cài panel: tự import nhạc, dựng comp đúng bố cục và motion đang xem trên web. |

## Chạy thử

1. Mở terminal trong thư mục này rồi chạy: `python -m http.server 8000`
2. Mở trình duyệt Chrome / Edge: http://localhost:8000/vi/
   (mở trực tiếp file `vi/index.html` cũng được, nhưng nên dùng cách trên)
3. Dán lời → **Chọn tệp** nhạc → bấm **✦ Tự căn lời (AI)**.
   Lần đầu tải model (~150–250 MB, sau đó trình duyệt lưu lại). Có GPU + WebGPU thì nhanh hơn nhiều.
   Model "Whisper small" chính xác hơn "base" nhưng nặng và chậm hơn.
4. Kiểm tra trên timeline; câu nào lệch thì bấm nhịp lại hoặc kéo marker như bình thường.
   **Xóa thời gian thủ công** = hoàn tác toàn bộ.
5. Chọn phong cách / Ngẫu nhiên như thường → **Xuất script AE (.jsx)**.
6. Đặt file `.jsx` và file nhạc **cùng một thư mục** → After Effects: **File › Scripts › Run Script File…**

## Mã nguồn đã sửa
- `src/12b_autosync.js` (mới): nút, nhận dạng giọng (transformers.js trong Web Worker), ánh xạ chữ ↔ thời gian, xuất `.jsx`.
- `src/08_planner.js`: dùng timing từng ký tự (`project.timing.auto`) để đặt điểm cắt cảnh và thời điểm câu biến mất.
- `src/12_ui.js`: "Xóa thời gian thủ công" xoá luôn timing tự động. `app/style.css`: 1 dòng CSS.
- Build lại trang: `python3 build.py`

## Áp vào repo JIZURA gốc
```
git clone https://github.com/852wa/JIZURA && cd JIZURA
git apply ../jizura-autosync.patch && cp ../AUTOSYNC.vi.md . && python3 build.py
```
