from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph
import base64
import re


class StructuredContent:
    """Represents a piece of structured content from a document."""
    
    def __init__(self, content_type, text, level=0, style=None, image_data=None):
        self.type = content_type
        self.text = text
        self.level = level
        self.style = style
        self.image_data = image_data


def extract_heading_level(paragraph):
    """Extract heading level from paragraph style."""
    style_name = paragraph.style.name if paragraph.style else ""
    
    if "Heading" in style_name:
        match = re.search(r'Heading\s*(\d+)', style_name)
        if match:
            return int(match.group(1))
    
    return None


def extract_structured_content(docx_path):
    """Extract content from DOCX with structure preservation."""
    doc = Document(docx_path)
    
    # Build image reference map (limit image size)
    image_map = {}
    image_count = 0
    
    for rel in doc.part.rels.values():
        if "image" in rel.reltype and not rel.is_external:
            try:
                image_blob = rel.target_part.blob
                # Only embed small images (< 300KB)
                if len(image_blob) < 300000:
                    base64_data = base64.b64encode(image_blob).decode('utf-8')
                    content_type = rel.target_part.content_type
                    data_url = f"data:{content_type};base64,{base64_data}"
                    image_map[rel.target_part.partname] = data_url
                    image_count += 1
                else:
                    print(f"      Skipping large image ({len(image_blob)/1024:.0f}KB)")
            except Exception as e:
                print(f"      Image error: {e}")
    
    if image_count > 0:
        print(f"    ✓ Embedded {image_count} images")
    
    structured_content = []
    
    for element in doc.element.body:
        if isinstance(element, CT_P):
            para = Paragraph(element, doc)
            
            # Check for images
            has_image = False
            for run in para.runs:
                for drawing in run.element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing'):
                    for blip in drawing.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip'):
                        embed_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                        if embed_id:
                            try:
                                rel = doc.part.rels[embed_id]
                                img_part_name = rel.target_part.partname
                                if img_part_name in image_map:
                                    structured_content.append(
                                        StructuredContent('image', '', image_data=image_map[img_part_name])
                                    )
                                    has_image = True
                            except:
                                pass
            
            # Process text
            if not has_image and para.text.strip():
                heading_level = extract_heading_level(para)
                
                if heading_level:
                    structured_content.append(
                        StructuredContent('heading', para.text.strip(), level=heading_level, style=para.style.name)
                    )
                else:
                    structured_content.append(
                        StructuredContent('paragraph', para.text.strip(), style=para.style.name if para.style else None)
                    )
        
        elif isinstance(element, CT_Tbl):
            table = Table(element, doc)
            table_text = "\n"
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells)
                table_text += row_text + "\n"
            
            if table_text.strip():
                structured_content.append(StructuredContent('table', table_text.strip()))
    
    return structured_content