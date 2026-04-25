"""
base.py - Publisher protocol for Pressroom.

This file defines the Publisher protocol (abstract base class) that all
publishers must implement. Publishers are responsible for taking generated
PDF content and delivering it to a destination (filesystem, blog, etc.).

DESIGN RATIONALE:
- Protocol ensures all publishers accept PDF path and metadata
- Factory pattern allows selecting publisher based on output type
- Adding a new publisher is simple: create new file, implement Publisher protocol

SPEC REFERENCE: §11 "Multi-Format Publishing"
         §11.1 "Publisher Protocol" (method signatures)
         §11.2 "Publisher Selection" (config.PUBLISHERS list)

DEPENDENCIES:
- This file is imported by: services/publishers/pdf.py, blog.py, docx.py
- Abstract base class - concrete implementations in publisher files

PUBLISHER SELECTION FLOW:
1. User publishes paper in UI
2. Router calls publisher.publish(pdf_path, metadata)
3. Factory selects publisher based on config.PUBLISH_FORMATS (e.g., ["pdf", "blog"])
4. Selected publisher's publish() method is called
5. PDF is saved to destination (filesystem, blog CMS, etc.)

TODO: Implement the Publisher abstract base class and factory function
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


class Publisher(ABC):
    """
    Abstract base class for all publishers.

    TODO: Implement the full Publisher protocol (see module docstring for design)

    ALL CONCRETE PUBLISHERS MUST:
    1. Inherit from Publisher
    2. Implement publish() method with exact signature
    3. Return dict with publication result info

    FACTORY USAGE:
        publisher = get_publisher("pdf")  # or "blog", "docx", etc.
        result = await publisher.publish(
            pdf_path=Path("/tmp/pressroom/my-paper/output.pdf"),
            metadata={"title": "My Paper", "author": "John Doe"}
        )
    """

    @abstractmethod
    async def publish(
        self,
        pdf_path: Path,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Publish a PDF to the destination.

        PARAMETERS:
        - pdf_path: Path to the generated PDF file
        - metadata: Dict with paper metadata (title, author, gate, version, etc.)

        RETURNS:
        - dict with publication result info:
          For PDF publisher: {"saved_to": "/path/to/pressroom-pubs/..."}
          For blog publisher: {"posted_to": "https://blog.example.com/post/..."}
          For docx publisher: {"saved_to": "/path/to/output.docx"}

        SIDE EFFECTS (varies by publisher):
        - PDF publisher: Copies PDF to pressroom-pubs repo directory
        - Blog publisher: Posts to blog CMS via API
        - DOCX publisher: Converts PDF to DOCX and saves

        MUST BE IMPLEMENTED BY:
        - PdfPublisher (services/publishers/pdf.py)
        - BlogPublisher (services/publishers/blog.py)
        - DocxPublisher (services/publishers/docx.py)
        """
        pass


def get_publisher(publisher_type: str) -> Publisher:
    """
    Factory function to select the correct publisher at runtime.

    TODO: Implement based on publisher_type:
        if publisher_type == "pdf":
            from services.publishers.pdf import PdfPublisher
            return PdfPublisher()
        elif publisher_type == "blog":
            from services.publishers.blog import BlogPublisher
            return BlogPublisher()
        elif publisher_type == "docx":
            from services.publishers.docx import DocxPublisher
            return DocxPublisher()
        else:
            raise ValueError(f"Unknown publisher type: {publisher_type}")
    """
    pass