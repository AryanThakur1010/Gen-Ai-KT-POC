from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
import base64

def extract_text_and_images(docx_path):
    """
    Extracts text and images from a Word document IN ORDER.
    Returns images as base64 data URLs positioned where they appear in the document.
    
    Returns:
        text: Full document text with image markers
        image_map: Dictionary mapping image markers to base64 data URLs
    """
    doc = Document(docx_path)
    
    # Build image reference map first
    image_map = {}
    for i, rel in enumerate(doc.part.rels.values()):
        if "image" in rel.reltype:
            if rel.is_external:
                print(f"    ⚠️  Skipping external image link")
                continue
            
            try:
                image_blob = rel.target_part.blob
                base64_data = base64.b64encode(image_blob).decode('utf-8')
                content_type = rel.target_part.content_type
                data_url = f"data:{content_type};base64,{base64_data}"
                
                # Store by relationship ID
                image_map[rel.target_part.partname] = data_url
                print(f"    ✓ Embedded image {i+1} ({len(base64_data)} bytes)")
                
            except Exception as e:
                print(f"    ⚠️  Could not embed image {i+1}: {str(e)}")
                continue
    
    # Extract content in order (paragraphs, tables, images)
    content_parts = []
    
    for element in doc.element.body:
        if isinstance(element, CT_P):
            para = Paragraph(element, doc)
            
            # Check if paragraph contains an image
            has_image = False
            for run in para.runs:
                for drawing in run.element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing'):
                    # Extract image reference
                    for blip in drawing.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip'):
                        embed_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                        if embed_id:
                            try:
                                rel = doc.part.rels[embed_id]
                                img_part_name = rel.target_part.partname
                                
                                if img_part_name in image_map:
                                    # Add image inline
                                    content_parts.append(f"\n![Image]({image_map[img_part_name]})\n")
                                    has_image = True
                            except:
                                pass
            
            # Add text if paragraph has content and no image
            if not has_image and para.text.strip():
                content_parts.append(para.text.strip())
        
        elif isinstance(element, CT_Tbl):
            table = Table(element, doc)
            # Simple table text extraction
            table_text = "\n"
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells)
                table_text += row_text + "\n"
            content_parts.append(table_text)
    
    full_text = "\n\n".join(content_parts)
    
    # Return text with inline images already embedded
    # Return empty list since images are now inline
    return full_text, []
