# Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
# Builds the Pressroom Docker image.
#
# Base image: pandoc/extra:latest-ubuntu
#   This comes with Pandoc and a full TeX Live installation pre-installed,
#   which is everything needed to run XeLaTeX for PDF generation.
#   See: https://github.com/pandoc/dockerfiles
#
# What this Dockerfile adds on top of the base image:
#   - Python 3 and pip (to run the FastAPI app)
#   - Common free fonts for XeLaTeX (Liberation, DejaVu, FreeFont)
#   - The Python dependencies from requirements.txt
#   - The app source code and static files
#
# Font note
# ─────────
# XeLaTeX can only use fonts physically installed in this image.
# The fonts installed here (Liberation, DejaVu, FreeFont) are good defaults
# that cover most use cases.  If your LaTeX template asks for a font that
# isn't listed here, add it with another apt-get install line below.
#
# Templates (LaTeX and prompt) are NOT bundled here — they are fetched from
# the GitHub pressroom repo at runtime, so updating a template only requires
# pushing to GitHub, not rebuilding this image.
# ─────────────────────────────────────────────────────────────────────────────

FROM pandoc/extra:latest-ubuntu

# Install Python, pip, and common fonts in a single layer to keep image size down.
# --no-install-recommends avoids pulling in large optional packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    # Liberation fonts: metrically compatible with Arial, Times New Roman, Courier New
    fonts-liberation \
    # DejaVu fonts: wide Unicode coverage, very commonly available
    fonts-dejavu \
    # GNU FreeFont: another full Unicode set (FreeSans, FreeSerif, FreeMono)
    fonts-freefont-ttf \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Refresh the font cache so XeLaTeX can find the newly installed fonts
RUN fc-cache -fv

WORKDIR /app

# Install Python dependencies first (before copying app code).
# Docker caches this layer — if only app code changes, pip doesn't re-run.
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy the app source code and static files.
# Templates and LaTeX files are fetched from GitHub at runtime — not here.
COPY *.py .
COPY routers/ ./routers/
COPY services/ ./services/
COPY static/ ./static/

EXPOSE 8000

# The pandoc/extra base image sets its own ENTRYPOINT — we override it here
# so the container runs uvicorn (the Python web server) instead of pandoc.
ENTRYPOINT []
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
