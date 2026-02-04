from fpdf import FPDF
from fpdf.enums import XPos, YPos
import os

class GoReportPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font('unicode', '', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C', new_x=XPos.RIGHT, new_y=YPos.TOP)

class PDFGenerator:
    def __init__(self):
        self.pdf = GoReportPDF()
        self._setup_fonts()

    def _setup_fonts(self):
        """日本語フォントの登録"""
        font_paths = [
            "C:\\Windows\\Fonts\\msgothic.ttc",
            "C:\\Windows\\Fonts\\meiryo.ttc",
            "C:\\Windows\\Fonts\\msmincho.ttc"
        ]
        font_found = False
        for path in font_paths:
            if os.path.exists(path):
                try:
                    self.pdf.add_font('unicode', '', path)
                    self.pdf.set_font('unicode', '', 12)
                    font_found = True
                    break
                except Exception as e:
                    print(f"Font load error for {path}: {e}")
                    continue
        if not font_found:
            self.pdf.set_font("Arial", size=12)

    def generate_report(self, title, items, summary, output_path):
        """title, items=[{'move':int, 'image':str, 'text':str}], summary, output_path"""
        self.pdf.add_page()
        
        # Title
        self.pdf.set_font('unicode', '', 20)
        self.pdf.cell(0, 20, title, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.pdf.ln(10)

        for item in items:
            # Title
            self.pdf.set_font('unicode', '', 16)
            title = item.get('title', f"第 {item.get('move', '?')} 手の解説")
            self.pdf.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.pdf.ln(5)
            
            # Image
            if item.get('image') and os.path.exists(item['image']):
                # 画像を中央寄せで配置
                self.pdf.image(item['image'], x=30, w=150)
                self.pdf.ln(5)
            
            # Text
            self.pdf.set_font('unicode', '', 11)
            self.pdf.multi_cell(0, 8, item['text'])
            self.pdf.ln(15)
            
            if self.pdf.get_y() > 230:
                self.pdf.add_page()

        # Summary Page
        self.pdf.add_page()
        self.pdf.set_font('unicode', '', 18)
        self.pdf.cell(0, 15, "黒番への総評", align='L', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.pdf.ln(5)
        self.pdf.set_font('unicode', '', 11)
        self.pdf.multi_cell(0, 8, summary)

        self.pdf.output(output_path)
        return output_path

if __name__ == "__main__":
    gen = PDFGenerator()
    test_items = [{"move": 24, "image": "", "text": "テスト解説文です。日本語表示の確認です。"}]
    gen.generate_report("囲碁AI対局レポート", test_items, "本日はお疲れ様でした。", "test_report.pdf")
    print(f"PDF generated: {os.path.abspath('test_report.pdf')}")