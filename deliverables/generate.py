"""Rebuild editable report and slide deck from tracked sources; no OpenAlex calls.

Run ``python deliverables/generate.py`` from the repository root. LibreOffice
converts the editable files to PDFs when installed; output PDFs are not faked.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt as PptPt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "deliverables/report/FINAL_ACADEMIC_REPORT.md"
REPORT = SOURCE.parent / "FINAL_ACADEMIC_REPORT.docx"
SLIDES = ROOT / "deliverables/presentation/FINAL_PRESENTATION.pptx"


def clean_markdown(text: str) -> str:
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    return re.sub(r"\*\*|`|\*", "", text)


def report_docx() -> None:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Cm(2.3)
    section.left_margin = section.right_margin = Cm(2.5)
    style = doc.styles["Normal"]
    style.font.name = "Liberation Serif"
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(6)
    in_code = False
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if line.startswith("```"):
            in_code = not in_code
            continue
        if not line:
            continue
        if line.startswith("!["):
            match = re.match(r"!\[([^]]*)\]\(([^)]+)\)", line)
            if match:
                path = (SOURCE.parent / match.group(2)).resolve()
                if not path.is_file():
                    raise FileNotFoundError(path)
                doc.add_picture(str(path), width=Cm(15))
                doc.add_paragraph(match.group(1), style="Caption")
            continue
        if line.startswith("# "):
            doc.add_heading(clean_markdown(line[2:]), 0)
        elif line.startswith("## "):
            doc.add_heading(clean_markdown(line[3:]), 1)
        elif line.startswith("### "):
            doc.add_heading(clean_markdown(line[4:]), 2)
        elif line.startswith("|") and i < len(lines) and lines[i].startswith("|---"):
            rows = [line]
            i += 1
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i]); i += 1
            matrix = [[clean_markdown(cell.strip()) for cell in row.strip("|").split("|")] for row in rows]
            table = doc.add_table(rows=0, cols=len(matrix[0]))
            table.style = "Table Grid"
            for row in matrix:
                cells = table.add_row().cells
                for j, value in enumerate(row):
                    cells[j].text = value
        else:
            doc.add_paragraph(clean_markdown(line), style="Normal")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(REPORT)


def presentation() -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    spec = [
        ("AI/CV Research Landscape", ["OpenAlex · 2020–2025 · Nhập môn Khoa học dữ liệu", "Phân tích dữ liệu + gợi ý chủ đề có người dùng xác nhận"], None),
        ("Câu hỏi & dữ liệu", ["RQ1–RQ4: xu hướng, trích dẫn, OA, hợp tác", "RQ5: bối cảnh tham khảo; RQ6: độ tin cậy nhãn chủ đề", "Tổng thể chính: 937.493 · mẫu gốc: 12.000 · mở rộng ML: 2.515"], None),
        ("RQ1 · Xu hướng xuất bản", ["Khung AI/CV định nghĩa chặt, không phải toàn bộ AI thế giới", "2020: 125.506; 2025: 232.476 (ảnh chụp OpenAlex)"], "reports/figures/phase4/rq1_population_counts.png"),
        ("RQ2 · Trích dẫn", ["Mẫu 12.000: trung vị 2, trung bình 11,24", "37,75% có 0 trích dẫn; trích dẫn phụ thuộc tuổi bài", "FWCI thiếu ở mọi preprint trong mẫu"], "reports/figures/phase4/rq2_citation_distribution.png"),
        ("RQ3 · Open Access", ["β nhị phân chưa điều chỉnh = −0,330 trên ln(1 + trích dẫn)", "Gold vs closed, đã điều chỉnh: β = +0,463; HC3 CI [0,396; 0,531]", "Green vs closed: β = +0,178; HC3 CI [0,087; 0,269]", "Liên hệ có điều kiện, không phải hiệu ứng nhân quả"], "reports/figures/phase4/rq3_adjusted_coefficients.png"),
        ("RQ4 · Hợp tác", ["Đồng liên kết quốc gia trong mẫu, không phải quốc tịch", "1.979/7.970 bài đủ thông tin có hợp tác quốc tế", "2.949 bài thiếu quốc gia liên kết"], "reports/figures/phase4/rq4_country_network.png"),
        ("RQ5 · Tài liệu tham khảo", ["289.110 cạnh tham khảo trong mẫu 12.000", "Pool lịch sử ≥2 bài dẫn: median ID overlap 12,1%", "NO-GO cho hệ gợi ý tài liệu là ML chính"], None),
        ("RQ6 · Nhãn chủ đề", ["14 chủ đề OpenAlex được chọn trước", "Nhãn bạc và chủ đề chồng lắp; chưa có đánh giá hai người chấm", "Mô hình học sự tương hợp với nhãn OpenAlex, không đo chân lý ngữ nghĩa"], None),
        ("So sánh mô hình", ["681 bài 2024 trong danh mục: SVM macro-F1 0,8808", "SVM chỉ mẫu gốc: 0,8506; NB/LR mở rộng: 0,8580", "2025 vẫn niêm phong; đây là kết quả phát triển"], "reports/figures/finalization_p3/model_comparison.png"),
        ("Open-set & giao diện", ["Chấp nhận nhầm ngoài danh mục: 21,66% (2024)", "Top 3 + từ chối + xác nhận thủ công", "Topic Explorer sử dụng được khi không có mô hình"], None),
        ("Tái lập & giới hạn", ["Raw, manifest, checksum và kiểm tra số mẫu", "Dữ liệu/mô hình không có trên public GitHub", "Chưa có chấm người thật; không suy luận nhân quả OA"], None),
        ("Kết luận", ["Nghiên cứu dữ liệu và giao diện khám phá có thể kiểm chứng", "Nguyên mẫu hỗ trợ, không gán nhãn tự động", "Bước tiếp: đánh giá người thật và rà soát phạm vi"], None),
    ]
    for number, (title, bullets, figure) in enumerate(spec, 1):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        bg = slide.background.fill
        bg.solid(); bg.fore_color.rgb = RGBColor(13, 27, 49)
        box = slide.shapes.add_textbox(Inches(.65), Inches(.5), Inches(12), Inches(.8))
        p = box.text_frame.paragraphs[0]
        p.text = title; p.font.size = PptPt(30); p.font.bold = True; p.font.color.rgb = RGBColor(112, 224, 209)
        text_width = 5.3 if figure else 11.8
        body = slide.shapes.add_textbox(Inches(.7), Inches(1.6), Inches(text_width), Inches(5.1)).text_frame
        body.word_wrap = True
        for j, item in enumerate(bullets):
            p = body.paragraphs[0] if j == 0 else body.add_paragraph()
            p.text = "• " + item; p.font.size = PptPt(20 if figure else 23)
            p.font.color.rgb = RGBColor(239, 245, 249)
            p.space_after = PptPt(18)
        if figure:
            path = ROOT / figure
            if not path.exists():
                raise FileNotFoundError(path)
            slide.shapes.add_picture(str(path), Inches(6.2), Inches(1.6), width=Inches(6.5))
        footer = slide.shapes.add_textbox(Inches(.7), Inches(7.05), Inches(12), Inches(.25)).text_frame.paragraphs[0]
        footer.text = f"AI Research Trends · {number}/12 · số liệu theo nguồn gốc ghi trong báo cáo"
        footer.font.size = PptPt(10); footer.font.color.rgb = RGBColor(161, 174, 190)
    SLIDES.parent.mkdir(parents=True, exist_ok=True)
    prs.save(SLIDES)


def pdf(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="lo_p4_") as profile:
        subprocess.run(["libreoffice", f"-env:UserInstallation=file://{profile}", "--headless",
                        "--convert-to", "pdf", "--outdir", str(path.parent), str(path)], check=True)
    if not path.with_suffix(".pdf").is_file():
        raise RuntimeError(f"PDF not generated for {path}")


if __name__ == "__main__":
    report_docx()
    presentation()
    pdf(REPORT)
    pdf(SLIDES)
    print(REPORT, REPORT.with_suffix(".pdf"), SLIDES, SLIDES.with_suffix(".pdf"), sep="\n")
