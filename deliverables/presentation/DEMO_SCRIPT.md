# Kịch bản trình diễn 5–7 phút

**Chuẩn bị:** tạo môi trường theo `docs/DEVELOPMENT_SETUP.md`, xác minh gói web và bundle mô hình, chạy `streamlit run dashboard/app.py --server.address 127.0.0.1`. Không mở tập kiểm thử 2025. Nếu không có artifact cục bộ, trình bày slide và nêu rõ ứng dụng không thể chạy từ clone công khai.

| Thời gian | Nội dung nói và thao tác | Thông điệp khoa học |
|---|---|---|
| 0:00–0:40 | Slide 1–2: mục tiêu nghiên cứu và ba phạm vi dữ liệu. Mở Home, chỉ số mẫu gốc và 14 chủ đề. | 937.493 là tổng thể trong khung AI/CV đã định nghĩa, 12.000 là mẫu, 2.515 mở rộng chỉ cho ML. |
| 0:40–1:30 | Research Landscape → RQ1, di chuột qua đường xu hướng; RQ2 xem trung vị trích dẫn. | 2025 có 232.476 bản ghi trong tổng thể; trích dẫn tuổi bài khác nhau, không phải điểm chất lượng. |
| 1:30–2:20 | RQ3 so sánh sáu trạng thái OA; slide hệ số điều chỉnh. | β Gold 0,463 và Green 0,178 là liên hệ có điều kiện trên `ln(1+citations)`, không nhân quả. |
| 2:20–3:00 | RQ4 hiển thị bảng đồng liên kết và mẫu số 7.970. | Thiếu quốc gia không bằng không hợp tác; không suy từ mẫu lên tất cả AI. |
| 3:00–3:40 | Topic Explorer chọn một trong 14 topic, đọc mô tả, biểu đồ tổng thể topic và bài mẫu. | Duyệt thủ công không cần mô hình; chuỗi chủ đề có thể chồng lắp. |
| 3:40–4:25 | Paper Explorer tìm từ khóa, lọc năm/topic; xem một bản ghi OpenAlex. | Chỉ tra 12.000 bài mẫu, không phải tìm kiếm toàn bộ OpenAlex. |
| 4:25–5:20 | Classify My Research: nhập một tiêu đề/tóm tắt hợp lệ do người trình diễn chuẩn bị, xem ba gợi ý và trạng thái; sau đó chủ động xác nhận một topic. | SVM margin không phải xác suất; không có gán nhãn tự động. Nếu mô hình vắng mặt, Topic Explorer vẫn dùng được. |
| 5:20–6:00 | Methodology & Model Evaluation, slide mô hình: macro-F1 0,8808 trên 681 bài 2024; outside false acceptance 21,66%. | Nhãn bạc, tập phát triển 2024, chưa có 2025 final test. |
| 6:00–6:30 | Slide cuối: mở báo cáo học thuật, nhấn vào manifest/checksum và tình trạng người chấm. | Sản phẩm là nguyên mẫu nghiên cứu có giới hạn, chờ đánh giá độc lập thật. |

**Dự phòng:** Nếu ứng dụng không khởi động do thiếu dữ liệu riêng tư, trình bày các hình và bảng đã xuất bản cùng log xác minh; không sử dụng dữ liệu giả hoặc tuyên bố đã demo trực tiếp. Không đưa thông tin API key hoặc tài liệu niêm phong lên màn hình.
