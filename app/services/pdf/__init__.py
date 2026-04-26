from .base import PDFEngine, get_pdf_engine

async def generate_pdf(slug, body, frontmatter, template_content):
    engine = get_pdf_engine()
    return await engine.generate(slug, body, frontmatter, template_content)