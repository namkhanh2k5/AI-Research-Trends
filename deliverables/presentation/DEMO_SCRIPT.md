# Kịch bản trình diễn 7–9 phút

**Chuẩn bị:** tạo môi trường theo `docs/DEVELOPMENT_SETUP.md`, xác minh gói web và bundle mô hình, chạy `streamlit run dashboard/app.py --server.address 127.0.0.1`. Không mở tập kiểm thử 2025. Nếu không có artifact cục bộ, trình bày slide và nêu rõ ứng dụng không thể chạy từ clone công khai.

| Thời gian | Nội dung nói và thao tác | Thông điệp khoa học |
|---|---|---|
| 0:00–0:40 | Slide 1–2: mục tiêu nghiên cứu và ba phạm vi dữ liệu. Mở Home, chỉ số mẫu gốc và 14 chủ đề. | 937.493 là tổng thể trong khung AI/CV đã định nghĩa, 12.000 là mẫu, 2.515 mở rộng chỉ cho ML. |
| 0:40–1:30 | Research Landscape → RQ1, di chuột qua đường xu hướng; RQ2 xem trung vị trích dẫn. | 2025 có 232.476 bản ghi trong tổng thể; trích dẫn tuổi bài khác nhau, không phải điểm chất lượng. |
| 1:30–2:20 | RQ3 so sánh sáu trạng thái OA; slide hệ số điều chỉnh. | β Gold 0,463 và Green 0,178 là liên hệ có điều kiện trên `ln(1+citations)`, không nhân quả. |
| 2:20–3:00 | RQ4 hiển thị bảng đồng liên kết và mẫu số 7.970. | Thiếu quốc gia không bằng không hợp tác; không suy từ mẫu lên tất cả AI. |
| 3:00–3:40 | Research Landscape → RQ5 và RQ6, xem pool tài liệu và chồng lắp nhãn; nêu quyết định NO-GO cho recommender. | ID overlap không phải retrieval recall; nhãn OpenAlex chưa được người thật thẩm định. |
| 3:40–4:20 | Topic Explorer chọn một trong 14 topic, đọc mô tả, xu hướng tổng thể, bối cảnh mẫu và bài đại diện. | Duyệt thủ công không cần mô hình; mỗi chỉ số có nguồn gốc. |
| 4:20–5:00 | Paper Explorer tìm từ khóa, lọc năm/topic; xem một bản ghi và DOI/OpenAlex. | Chỉ tra 12.000 bài mẫu, không phải tìm kiếm toàn bộ OpenAlex. |
| 5:00–6:10 | Classify My Research: nhập tiêu đề/tóm tắt ví dụ, xem top 3 và trạng thái; chọn chủ đề khác gợi ý nếu phù hợp rồi xác nhận Topic Brief. Sửa một từ trong bản thảo và chỉ ra gợi ý cũ bị xóa. | SVM margin không phải xác suất; không gán nhãn tự động và không giữ xác nhận cũ khi input đổi. |
| 6:10–7:00 | Methodology & Model Evaluation: bảng so sánh, F1 theo lớp, ma trận nhầm lẫn, open-set. | Macro-F1 0,8808 trên 681 bài 2024; outside false acceptance 21,66%; 2025 vẫn SEALED. |
| 7:00–7:40 | Mở báo cáo PDF từ nút tải trong app, nêu manifest/checksum và tình trạng người chấm. | Website là nguyên mẫu nghiên cứu cục bộ; chưa có đánh giá người dùng thực. |

**Dự phòng:** Nếu ứng dụng không khởi động do thiếu dữ liệu riêng tư, trình bày các hình và bảng đã xuất bản cùng log xác minh; không sử dụng dữ liệu giả hoặc tuyên bố đã demo trực tiếp. Không đưa thông tin API key hoặc tài liệu niêm phong lên màn hình.

**Lần diễn tập Phase 4.1:** Chrome/Playwright cục bộ đã đi qua thao tác dự đoán → top ba → ghi đè thủ công → xác nhận → Topic Brief, thay input, RQ5/RQ6, Paper Explorer không có kết quả và tải báo cáo. Các ảnh chụp ở `data/analysis/finalization_p4_1_browser_evidence/` là bằng chứng cục bộ; bản công khai của hai ảnh không nhạy cảm nằm trong `figures/`. Đây không phải khảo sát khả dụng với người dùng thật.
