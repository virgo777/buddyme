# Post-Install Setup

MarkItDown skill installed! Here's how to get started.

## 1. Verify Installation

```bash
markitdown --version
```

If not found, install the CLI:
```bash
pip install 'markitdown[all]'
```

## 2. Test It

```bash
# Convert a PDF
markitdown document.pdf -o output.md

# Convert a URL
markitdown https://example.com -o page.md
```

## 3. Add to Agent Instructions (Recommended)

Add to your `AGENTS.md`:

```markdown
## Document Conversion
When fetching documentation or converting files:
- Use `markitdown <url>` instead of curl/wget for web docs
- Use `markitdown <file>` to convert PDFs, Word, Excel, etc.
- Output is clean markdown optimized for LLM analysis
```

## 4. Install Format-Specific Dependencies

Only install what you need:

```bash
pip install 'markitdown[pdf]'      # PDF support
pip install 'markitdown[docx]'     # Word documents
pip install 'markitdown[pptx]'     # PowerPoint
pip install 'markitdown[xlsx]'     # Excel
pip install 'markitdown[audio-transcription]'   # Audio
pip install 'markitdown[youtube-transcription]' # YouTube
```

Or install everything:
```bash
pip install 'markitdown[all]'
```

## 5. System Dependencies (Optional)

### OCR (for images)
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract
```

## Quick Reference

```bash
# File conversion
markitdown file.pdf -o output.md

# URL conversion
markitdown https://example.com -o page.md

# Batch conversion
python ~/.openclaw/skills/markitdown/scripts/batch_convert.py docs/*.pdf -o markdown/ -v
```

## Troubleshooting

**"markitdown not found"**
```bash
pip install 'markitdown[all]'
```

**"No module named 'xxx'"**
```bash
pip install 'markitdown[pdf]'  # or docx, pptx, etc.
```

**OCR not working**
```bash
sudo apt-get install tesseract-ocr
```
