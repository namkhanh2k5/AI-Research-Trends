# PHÂN TÍCH XU HƯỚNG NGHIÊN CỨU AI/CV VÀ HỆ THỐNG HỖ TRỢ KHÁM PHÁ CHỦ ĐỀ DỰA TRÊN OPENALEX

**Báo cáo dự án Nhập môn Khoa học dữ liệu · Bản thảo có thể tái tạo · 01/11/2026**

> Báo cáo này trình bày kết quả đã kiểm chứng, không phải bằng chứng một hệ thống phân loại chủ đề tự động đã được thẩm định bởi chuyên gia. Đánh giá ngữ nghĩa của hai người chấm còn thiếu; tập kiểm thử 2025 chưa được mở.

## Tóm tắt

Dự án xây dựng quy trình thu thập, chuẩn hóa, phân tích thống kê và học máy trên dữ liệu học thuật OpenAlex. Khung nghiên cứu được định nghĩa chặt: công trình công bố từ 2020-01-01 đến 2025-12-31, thuộc loại article/review/preprint, có *primary subfield* 1702 (Artificial Intelligence) hoặc 1707 (Computer Vision and Pattern Recognition); ấn phẩm bị rút khỏi xuất bản được loại khỏi ước lượng chính. Tổng thể không đồng nghĩa với “mọi nghiên cứu AI trên thế giới”. Số liệu xu hướng được lấy từ tổng hợp trên toàn khung OpenAlex, tách biệt với mẫu chi tiết 12.000 công trình. Mẫu cho phép nghiên cứu trích dẫn, truy cập mở (OA), hợp tác và khám phá giấy tờ, nhưng xác suất chọn của API chưa được chứng minh, vì vậy trọng số mẫu chỉ mang tính danh nghĩa.

Phân tích mô tả và hồi quy làm rõ tác động của tuổi bài báo, kiểu công trình và dữ liệu thiếu. Thành phần ML dự đoán nhãn chủ đề chính do OpenAlex gán cho 14 chủ đề chọn trước, dùng TF-IDF và Linear SVM; macro-F1 trên 681 công trình phát triển năm 2024 là 0,8808. Tỷ lệ chấp nhận nhầm ngoài danh mục đạt 21,66% trong đánh giá phát triển, lớn hơn mục tiêu hiệu chỉnh. Sản phẩm cuối là trang khám phá dữ liệu cục bộ và công cụ *gợi ý cần người dùng xác nhận*, không phải bộ phân loại được kiểm định trên 2025 hay một thước đo chất lượng khoa học.

**Từ khóa:** OpenAlex; thư mục học; trí tuệ nhân tạo; thị giác máy tính; truy cập mở; TF-IDF; Linear SVM; nhãn bạc.

## 1. Giới thiệu

### 1.1 Bối cảnh và vấn đề

Người mới tham gia nghiên cứu AI/CV đối diện lượng công trình lớn, thay đổi nhanh, nhiều thuật ngữ và bằng chứng trích dẫn không đồng đều. Các trang tìm kiếm học thuật cung cấp bản ghi nhưng ít khi phân biệt rạch ròi số liệu tổng thể với mẫu chi tiết hoặc nêu độ bất định của nhãn chủ đề. Mục tiêu của dự án là tạo một nghiên cứu Khoa học dữ liệu tái lập được đồng thời cung cấp giao diện tra cứu có phạm vi rõ ràng.

### 1.2 Câu hỏi nghiên cứu

RQ1: Số công trình và chủ đề nghiên cứu trong khung AI/CV đã thay đổi như thế nào giai đoạn 2020–2025? RQ2: Chỉ báo trích dẫn khác nhau ra sao giữa năm, loại công trình và phân ngành? RQ3: OA liên hệ với chỉ báo trích dẫn như thế nào sau khi xét yếu tố thành phần? RQ4: Dữ liệu liên kết cơ quan và quốc gia thể hiện hợp tác ra sao? RQ5: Mạng tài liệu tham khảo trong mẫu có đặc điểm gì, và có đủ cho hệ gợi ý tài liệu hay không? RQ6: Nhãn chủ đề OpenAlex phù hợp đến đâu để xây dựng bài toán phân loại văn bản có giới hạn?

### 1.3 Đóng góp và phạm vi

Đóng góp gồm: khung chọn công trình và nhật ký truy xuất có checksum; bảng phân tích quan hệ; đánh giá thiếu dữ liệu; kết quả RQ1–RQ6 có mẫu số rõ; so sánh mô hình theo thời gian; chính sách từ chối ngoài danh mục; giao diện sáu chức năng có chỉ dẫn giới hạn. Phân tích không bao phủ mọi ngành AI, không xác định quan hệ nhân quả OA–trích dẫn, không xác lập độ đúng ngữ nghĩa nếu chưa có chấm độc lập.

## 2. Cơ sở lý thuyết và nghiên cứu liên quan

OpenAlex là đồ thị tri thức học thuật có thực thể công trình, tác giả, tổ chức và chủ đề [1], [2]. Một công trình có thể mang nhiều chủ đề; *primary topic* là nhãn một giá trị và được gán bằng mô hình của OpenAlex, không phải nhãn chuẩn của chuyên gia [3]. Chỉ số trích dẫn bị ảnh hưởng bởi tuổi công trình và phạm vi ngành; số lần trích dẫn không đồng nhất với chất lượng. FWCI hỗ trợ so sánh tương đối trong giới hạn dữ liệu có sẵn, nhưng thiếu có hệ thống ở preprint trong mẫu này.

TF-IDF biểu diễn tầm quan trọng tương đối của thuật ngữ trong tập văn bản [4]. Complement Naive Bayes, Logistic Regression và Linear SVM tạo ba giả định học khác nhau; việc fit vectorizer chỉ trên tập huấn luyện giúp tránh rò rỉ dữ liệu [5], [6]. Mô hình chỉ học tương quan giữa văn bản tiêu đề/tóm tắt và nhãn chính OpenAlex. Dù đạt điểm cao so với nhãn bạc, nó vẫn có thể lặp lại sai lệch gán nhãn của nguồn. Công cụ khám phá tài liệu dựa trên đồ thị tham khảo được xem xét ở RQ5 nhưng đã bị loại khỏi nhiệm vụ ML chính do độ phủ ứng viên thấp [7].

## 3. Thu thập dữ liệu và thiết kế mẫu

### 3.1 Hai lớp dữ liệu

Lớp **tổng thể** gồm các yêu cầu tổng hợp OpenAlex trên bộ lọc ngày, loại, primary subfield và trạng thái rút bài nhất quán. Lớp **chi tiết** gồm 12.000 Work ID duy nhất, phân tầng theo năm 2020–2025. Số mẫu theo năm lần lượt là 1.607; 1.650; 1.615; 1.865; 2.287; 2.976. Tổng thể chính không rút bài tại thời điểm thu thập Phase 2 là **937.493** công trình; tổng thể bao gồm rút bài để phân tích nhạy cảm là **942.825** [8]. Đây là ảnh chụp dữ liệu thay đổi theo thời gian, không phải hằng số toàn cục.

### 3.2 Thu thập và kiểm toán

Quy trình dùng API có xác thực, giới hạn tốc độ, phân trang, lưu phản hồi gốc, manifest và SHA-256. 123 trang dữ liệu đã được xác minh; 12.000 ID chuẩn không trùng, raw và interim JSONL khớp checksum [8]. Phân bổ theo năm dùng phương pháp số dư lớn nhất từ số dân số mỗi tầng; xác suất chọn và trọng số tính từ kế hoạch được gọi là *danh nghĩa* vì OpenAlex không cam kết thiết kế lấy mẫu xác suất. Không dùng một mẫu cân bằng theo chủ đề để suy ra độ phổ biến trong tổng thể.

### 3.3 Mở rộng dữ liệu ML

2.515 bản ghi bổ sung được thu thập có chủ đích để tăng hỗ trợ các chủ đề của huấn luyện lịch sử, tạo 14.515 bản ghi nguồn và 14.470 nhóm phiên bản [9]. Tập mở rộng chỉ phục vụ ML, không được đưa vào số liệu xu hướng, trích dẫn, OA hoặc hợp tác của tổng thể/mẫu gốc. Việc tăng hỗ trợ lớp không làm mẫu trở nên đại diện cho dân số AI/CV.

## 4. Tiền xử lý và kỹ thuật dữ liệu

Phản hồi OpenAlex là JSON lồng nhau: `primary_topic`, danh sách `topics`, `authorships`, `institutions`, `countries_distinct`, `referenced_works`, OA và chỉ mục đảo của abstract. Mỗi Work ID chuẩn hóa thành một dòng ở bảng works; các quan hệ nhiều-nhiều nằm trong bảng `work_topics`, `authorships`, `work_institutions`, `work_countries`, `references`, `category_membership`. Bảng `population_year_counts` được tạo từ tổng hợp đã kiểm chứng, không suy ra bằng 12.000 bản ghi [10].

Tiêu đề, DOI và tóm tắt thiếu được giữ null; abstract chỉ được dựng lại khi chỉ mục đảo hợp lệ. Mẫu Phase 2 có 2.558 tóm tắt, 2.678 FWCI, 2.902 thông tin tổ chức và 2.949 thông tin quốc gia không sẵn có; không thay FWCI thiếu bằng 0 [8]. Toàn bộ 2.678 preprint trong mẫu thiếu FWCI, nên so sánh theo FWCI loại trừ một kiểu công trình có hệ thống. Trích dẫn 0 được giữ như giá trị thật; ngoại lệ trích dẫn cao không bị xóa. Quốc gia là nơi liên kết cơ quan, không phải quốc tịch tác giả.

Phân tách ML theo thời gian: huấn luyện 2020–2023, phát triển 2024, kiểm thử 2025 giữ kín. Nhóm phiên bản ở cùng phía của phân tách để giảm rò rỉ do bài trùng/phiên bản. `TfidfVectorizer` được fit trong từng fold huấn luyện, không học từ 2024 hoặc 2025. Trước mỗi bước, manifest và checksum được đối chiếu; xuất bảng dùng định dạng Parquet có schema ổn định.

## 5. Khám phá dữ liệu và phân tích thống kê

### 5.1 RQ1 — Xu hướng công bố

Bảng 1 là số đếm toàn bộ khung chính không rút bài; không phải ước lượng từ mẫu. Giai đoạn 2020–2025, số quan sát tăng từ 125.506 lên 232.476; riêng 2025 tăng 30,10% so với 2024 trong ảnh chụp OpenAlex đã lưu [11]. Điều này mô tả số bản ghi OpenAlex trong khung, không chứng minh tốc độ sản xuất tri thức toàn cầu tương ứng. Khả năng lập chỉ mục hồi tố và thay đổi bộ phân loại chủ đề có thể làm thay đổi chuỗi sau này.

| Bảng 1. Năm | Số công trình trong tổng thể chính | Tăng trưởng năm sau/năm trước |
|---|---:|---:|
| 2020 | 125.506 | — |
| 2021 | 128.893 | 2,70% |
| 2022 | 126.189 | −2,10% |
| 2023 | 145.735 | 15,49% |
| 2024 | 178.694 | 22,62% |
| 2025 | 232.476 | 30,10% |

![Hình 1. Số công trình theo năm trong tổng thể AI/CV chính; dữ liệu tổng hợp OpenAlex.](../../reports/figures/phase4/rq1_population_counts.png)

Chủ đề gốc OpenAlex, phân ngành và các nhãn từ quy tắc văn bản (LLM, RAG, đa phương thức) là các tầng đo khác nhau. Nhãn từ văn bản có thể chồng lắp, bỏ sót bài thiếu abstract và không thể đối chiếu số đếm như thể cùng phương pháp phân loại.

### 5.2 RQ2 — Trích dẫn

Trên 12.000 công trình mẫu gốc, trung vị trích dẫn là 2, trung bình 11,24, phân vị 90 là 23 và tối đa 4.199; 37,75% có 0 trích dẫn [11]. Phân phối lệch phải mạnh, do vậy trung vị và phân phối theo năm hữu ích hơn việc chỉ so sánh trung bình. Tuổi bài và loại công trình giải thích một phần khác biệt quan sát; không suy luận chất lượng nghiên cứu từ trích dẫn thô. FWCI chỉ phân tích trên công trình có quan sát, đặc biệt không đại diện cho preprint trong mẫu.

![Hình 2. Phân phối trích dẫn của mẫu chi tiết 12.000 công trình, không phải tổng thể.](../../reports/figures/phase4/rq2_citation_distribution.png)

### 5.3 RQ3 — Open Access và trích dẫn

Mô hình nhị phân chưa điều chỉnh (`unadjusted_binary`) gộp mọi trạng thái OA: hệ số OA so với closed là β = −0,330 trên `ln(1 + citations)`. Mô hình chính (`adjusted_status_year`) tách sáu trạng thái OA, kiểm soát năm công bố, loại bài và primary subfield với sai số chuẩn HC3. Gold so với closed: β = +0,463; khoảng tin cậy 95% [+0,396; +0,531]. Green so với closed: β = +0,178; khoảng tin cậy 95% [+0,087; +0,269] [11]. Hệ số dương là *liên hệ có điều kiện trong mô hình log(1 + trích dẫn)*, không phải OA gây tăng trích dẫn hay tăng chất lượng. `100(exp(0,463) − 1) ≈ 58,9%` là chênh lệch trung bình hình học có điều kiện của **1 + trích dẫn** dưới giả định mô hình; không phải “58,9% trích dẫn thô nhiều hơn trên mỗi bài”.

Nhóm Green gồm 3.559 công trình, trong đó 2.506 preprint; toàn bộ 2.678 preprint mẫu thiếu FWCI. Do thành phần nhóm khác nhau, không xem kết quả hai mô hình là “đảo dấu nhân quả”. Nhiễu chưa đo, lựa chọn xuất bản và đặc tả mô hình vẫn có thể ảnh hưởng kết quả.

![Hình 3. Hệ số hồi quy OA đã điều chỉnh trên thang log(1 + trích dẫn), mẫu chi tiết.](../../reports/figures/phase4/rq3_adjusted_coefficients.png)

### 5.4 RQ4 — Hợp tác

Mạng hợp tác được dựng từ **đồng liên kết cơ quan trong mẫu**, không phải toàn mạng cộng tác AI/CV. Có 2.902 bài không có tổ chức và 2.949 bài không có quốc gia được quan sát; các trường hợp này không được mã hóa là “không hợp tác” [11]. Trong 7.970 bài đủ dữ liệu để xét hợp tác quốc tế, 1.979 có nhiều hơn một quốc gia liên kết (24,83%). Tỷ lệ này có điều kiện trên mẫu số đã biết, không đại diện cho 12.000 bài hay toàn dân số.

![Hình 4. Mạng đồng liên kết quốc gia của các công trình có thông tin trong mẫu chi tiết.](../../reports/figures/phase4/rq4_country_network.png)

### 5.5 RQ5 — Bối cảnh tham khảo

12.000 bài mẫu chứa 289.110 cạnh tham khảo duy nhất đến 207.102 Work ID được dẫn. 7.529 bài có danh sách tham khảo không rỗng; 4.471 danh sách quan sát được rỗng [7]. Độ phủ ứng viên lịch sử yếu: dùng mọi bài dẫn trước 2023, pool có ít nhất hai bài dẫn lịch sử đạt trung vị ID-overlap 12,1% trên 909 truy vấn năm 2023. Hệ truy xuất chẩn đoán giới hạn metadata đạt mean end-to-end Recall@20 2,53%; vì vậy **NO-GO** cho hệ gợi ý tài liệu trích dẫn là ML chính. Số ID được nhắc đến không đánh giá độ phù hợp của tài liệu chưa được dẫn.

### 5.6 RQ6 — Tính phù hợp của nhãn chủ đề

14 lớp có 3.355 ví dụ huấn luyện đủ điều kiện; 681 ví dụ validation trong danh mục năm 2024 [12]. Các chủ đề gốc chồng lấp, nhất là cặp T10028/T10181. Thiếu abstract phụ thuộc chủ đề; với một số chủ đề đạt hơn 30% trong tập gốc 2020–2024. Việc nhãn OpenAlex và mô hình bất đồng không chứng minh mô hình sai hoặc đúng về mặt ngữ nghĩa. Không có kết quả đánh giá của hai người chấm độc lập; độ đúng của nhãn và ranh giới chủ đề còn mở.

## 6. Phương pháp học máy

Bài toán: từ title và abstract, xếp hạng 14 primary-topic nhãn bạc OpenAlex đã đóng băng. Đầu vào không chứa citation, Work ID, năm, OA hoặc topic score. Dữ liệu lịch sử 2020–2023 gồm 7.002 bài đủ điều kiện; 3.355 bài thuộc 14 chủ đề. 2024 có 1.843 bài gốc đủ điều kiện để phát triển; 681 thuộc danh mục. 2025 có 2.318 bài đủ điều kiện nhưng **không được đọc cho việc chọn mô hình hay báo cáo này** [9].

Baseline gồm lớp chiếm đa số và khớp TF-IDF với mô tả chủ đề. Ba mô hình có giám sát là ComplementNB, Logistic Regression, Linear SVM. Tối ưu tham số bằng `StratifiedGroupKFold` ba fold trên lịch sử, nhóm phiên bản không tách đôi. Macro-F1 trung bình đều theo lớp; accuracy và F1 theo lớp được báo cáo cùng mẫu số. SVM dùng từ đơn/cặp từ TF-IDF, `min_df=2`, tối đa 50.000 đặc trưng, `sublinear_tf=True`, C=1.

Không có lớp OTHER chắc chắn trong danh mục chính. Điểm biên SVM cho phép từ chối/giảm mức tin tưởng dựa trên ngưỡng hiệu chỉnh 2024; điểm biên **không phải xác suất**. Mọi dự đoán đều yêu cầu xác nhận của người dùng. Đánh giá ngữ nghĩa thật cần phiếu mù của hai người chấm và thảo luận bất đồng; hiện chưa có phiếu hoàn tất.

## 7. Kết quả thực nghiệm

| Bảng 2. Phương pháp | Macro-F1 trên 681 bài 2024 | Accuracy |
|---|---:|---:|
| Lớp đa số | 0,0248 | 0,2100 |
| Khớp mô tả chủ đề | 0,5522 | 0,5742 |
| ComplementNB, dữ liệu mở rộng | 0,8580 | 0,8532 |
| Logistic Regression, dữ liệu mở rộng | 0,8580 | 0,8649 |
| Linear SVM, chỉ mẫu gốc lịch sử | 0,8506 | — |
| Linear SVM, dữ liệu lịch sử mở rộng | **0,8808** | **0,8796** |

Các giá trị thuộc cùng tập validation 681 bài trong danh mục, ngoại trừ đối chiếu mở rộng/chỉ-gốc dùng cùng tập 2024 nhưng hai tập huấn luyện khác nhau [9]. Khoảng bootstrap ghép cặp 500 lần cho hiệu macro-F1 SVM mở rộng trừ chỉ-gốc là [0,0084; 0,0527]; đây không phải độ bất định của nhãn bạc hay quá trình lấy mẫu tổng thể. 82/681 dự đoán SVM không trùng nhãn chính OpenAlex; 48/82 nhãn dự đoán xuất hiện ở chủ đề thứ cấp, một dấu hiệu mơ hồ chứ không xác nhận đúng.

![Hình 5. Đối chiếu mô hình trên tập phát triển 2024; nhãn mục tiêu do OpenAlex gán.](../../reports/figures/finalization_p3/model_comparison.png)

Đánh giá open-set phát triển chia theo nhóm phiên bản: 738 bài hiệu chỉnh và 1.105 bài kiểm tra nội bộ (408 trong danh mục, 697 ngoài). Ngưỡng biên cố định −0,22227267687798036 đặt để giới hạn chấp nhận nhầm ngoài danh mục ≤20% trên hiệu chỉnh. Trên nhóm kiểm tra nội bộ, chấp nhận đúng phạm vi 83,09%, chấp nhận nhầm ngoài danh mục **21,66%**, AUROC 0,8919, tỷ lệ chấp nhận đúng chủ đề / mọi bài đủ điều kiện **28,33%** [9]. Mục tiêu 20% không đạt trên đánh giá phát triển. Tập kiểm thử 2025 vẫn **SEALED**, không có metric cuối cùng.

## 8. Thiết kế và triển khai hệ thống

Giao diện dùng Streamlit và Plotly trên dữ liệu cục bộ đã được xác minh. Lớp `ResearchData` cung cấp tổng quan, xu hướng, Topic Brief, tìm kiếm 12.000 giấy tờ và thống kê OA/trích dẫn/hợp tác. Sáu trang: Home, Research Landscape, Topic Explorer, Classify My Research, Paper Explorer, Methodology & Model Evaluation. Topic Explorer duyệt trực tiếp qua dữ liệu, không tải mô hình. Chỉ trang phân loại mới nạp bundle SVM có kiểm tra checksum, giới hạn input và trả top ba nhãn cùng trạng thái `confident_suggestion`, `needs_user_confirmation` hoặc `no_confident_match`. Chọn chủ đề là hành động riêng của người dùng, lưu trong phiên web chứ không sửa nguồn OpenAlex.

Mô hình `joblib` chỉ được tải từ gói đáng tin cậy đã được đối chiếu manifest; checksum không biến một pickle không tin cậy thành an toàn. Tên bài từ OpenAlex được hiển thị dưới dạng văn bản, không chèn HTML thô. Ứng dụng không gửi API trong vận hành thông thường. Trang reviewer riêng chỉ cho localhost, tách reviewer A/B và không hiện nhãn thật/dự đoán. Khóa kiểm thử 2025 dùng cổng phê duyệt sẵn có cộng registry tạo độc quyền; registry chỉ là biện pháp kỹ thuật tại một máy, không thay thế quản trị dự án hoặc ngăn clone khác.

## 9. Kiểm thử và đánh giá hệ thống

Các bài kiểm thử ngoại tuyến kiểm tra API, chuẩn hóa, tính toàn vẹn bảng, phương pháp, huấn luyện và phần web. Kiểm tra UI dùng Streamlit AppTest cho Home; kiểm tra service yêu cầu xác nhận và duyệt Topic Brief không nạp mô hình. Gói web và model được verifier đọc trước khi chạy; tài liệu triển khai chứa lệnh khởi chạy và kiểm tra HTTP health. Kết quả chạy cuối, phiên bản phụ thuộc và giới hạn thử nghiệm được ghi tại `reports/FINALIZATION_P4_TESTING_REPORT.md`; không khẳng định có người dùng tham gia thử nghiệm nếu chưa có dữ liệu thực.

## 10. Thảo luận và hạn chế

Thiết kế lấy mẫu qua API không bảo đảm xác suất chọn. Thiếu abstract làm giới hạn cả phân loại từ ngữ và phân tích nhãn; thiếu FWCI ở tất cả preprint làm so sánh chỉ dựa vào subset. DOI/affiliation thiếu, độ tuổi bài, thay đổi OpenAlex và chủ đề chồng lắp khiến kết luận chỉ mang tính mô tả. Mô hình mục tiêu là sự tương hợp với nhãn bạc, không phải tri thức chủ đề do chuyên gia xác lập. Tỷ lệ chấp nhận nhầm ngoài danh mục 21,66% là rủi ro sử dụng quan trọng; ứng dụng phải hiển thị sự dè dặt. Phân tích OA là quan sát, không nhận dạng tác động nhân quả. Website cục bộ có giá trị giáo dục và hỗ trợ khám phá, chưa có chứng cứ sử dụng thực tế rộng rãi hay khả năng vận hành công khai với gói dữ liệu/model Git-ignored.

Tập 2025 được bảo vệ theo giao thức đóng băng và chỉ có thể mở một lần sau khi nhận hai đánh giá độc lập, quyết định phạm vi, xác nhận checksum và phê duyệt rõ ràng. Mô hình cuối hiện tại là bundle lịch sử 2020–2023; không âm thầm thay bằng mô hình được fit thêm 2024. Registry cục bộ không thể ngăn một clone trái phép mở tập khác; trách nhiệm quản trị và kiểm toán vẫn thiết yếu.

## 11. Kết luận

Dự án hoàn tất một chuỗi nghiên cứu Khoa học dữ liệu có phân định dân số–mẫu, kiểm tra nguồn và báo cáo phương pháp. Dữ liệu OpenAlex cho thấy xu hướng tăng mạnh trong khung AI/CV đã định nghĩa; phân tích trích dẫn/OA/hợp tác đòi hỏi xét tuổi bài, thiếu dữ liệu và thành phần nhóm. Hệ ML SVM có độ khớp tốt với nhãn bạc trên phát triển 2024 nhưng chưa đủ căn cứ cho gán nhãn tự động. Kết quả phù hợp nhất là **nguyên mẫu hỗ trợ người dùng, có thể duyệt chủ đề thủ công và xác nhận gợi ý**, trong khi đánh giá người thật và bài kiểm thử 2025 vẫn là việc cần thực hiện trước khi tuyên bố khả năng tổng quát cuối cùng.

## Phụ lục A — Lệnh tái tạo cục bộ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,web,deliverables]"
openalex-build-web-data verify data/analysis/finalization_p2_web_data_20261101_v3
openalex-verify-final-ml data/analysis/finalization_p3_models_20261101_v1
streamlit run dashboard/app.py --server.address 127.0.0.1
pytest -q -ra
```

Không tải dữ liệu/mô hình từ GitHub vì các artifact này được loại khỏi Git; xem manifest và hướng dẫn tái tạo riêng. Không chạy `openalex-final-test` khi chưa có xác nhận chính thức.

## Phụ lục B — Từ điển dữ liệu rút gọn

`works` một dòng/Work ID; `work_topics`, `work_institutions`, `work_countries`, `references` là quan hệ nhiều-nhiều không nhân bản số bài; `category_membership` tách native/custom; `population_year_counts` chỉ từ tổng hợp đã xác minh; `paper_index` chỉ gồm 12.000 bài mẫu gốc. Các cột dẫn xuất `log1p_citations`, `has_fwci`, `international_collaboration` phải giữ null/unknown thích hợp [10].

## Tài liệu tham khảo (IEEE)

[1] J. Priem, H. Piwowar, R. Orr, “OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts,” 2022. https://arxiv.org/abs/2205.01833

[2] OpenAlex, “Works overview,” tài liệu chính thức, truy cập 01/11/2026. https://help.openalex.org/data/works/

[3] OpenAlex, “Topics – Aboutness,” tài liệu chính thức, truy cập 01/11/2026. https://help.openalex.org/data/topics/

[4] G. Salton, C. Buckley, “Term-weighting approaches in automatic text retrieval,” *Information Processing & Management*, vol. 24, no. 5, pp. 513–523, 1988. https://doi.org/10.1016/0306-4573(88)90021-0

[5] scikit-learn, “TfidfVectorizer,” tài liệu chính thức. https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html

[6] scikit-learn, “LinearSVC,” tài liệu chính thức. https://scikit-learn.org/stable/modules/generated/sklearn.svm.LinearSVC.html

[7] Dự án, `reports/PHASE5_FINAL_DECISION.md` và `reports/PHASE5_REFERENCE_EDA_REPORT.md`, phiên bản repository này.

[8] Dự án, `reports/PHASE2_COLLECTION_REPORT.md` và manifest thu thập đã kiểm chứng, phiên bản repository này.

[9] Dự án, `reports/FINALIZATION_P3_FINAL_ML_REPORT.md`, `FINALIZATION_P3_OPEN_SET_EVALUATION.md`, phiên bản repository này.

[10] Dự án, `docs/DATA_DICTIONARY.md` và `docs/FINALIZATION_P2_WEB_DATA_CONTRACT.md`, phiên bản repository này.

[11] Dự án, `reports/PHASE4_ANALYSIS_REPORT.md` và gói dữ liệu web Phase 2 cuối, phiên bản repository này.

[12] Dự án, `reports/FINALIZATION_P2_RQ6_TOPIC_LABEL_ANALYSIS.md`, phiên bản repository này.
