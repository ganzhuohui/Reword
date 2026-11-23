# Reword
An intelligent article rewriting tool powered by local AI. Extracts content from webpages, plain text, or PDF files, then rewrites it using a local Ollama model, with extensive controls for the output style.

## ✨ Features
    Extract content from multiple sources — Supports webpage URLs, pasted plain text, and PDF files    
    AI-powered rewriting — Uses local Ollama models, with streaming output    
    Fine-grained controls — 15 configurable parameters    
    User-friendly desktop interface — A modern GUI built with PySide6 (Qt), featuring real-time progress updates and streaming output preview    
    Export in multiple formats — Save as TXT or DOCX

## 📦 Installation

**Requirements**
    Python 3.10+
    Ollama installed and running with an AI model

**Steps**
### Clone the repository
git clone https://github.com/ganzhuohui/Reword.git
cd Reword


### Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate   # Windows

### Install dependencies
pip install -r requirements.txt

### Launch the application
python main.py

## 🏗️ Project Structure

reword/

├── main.py              # Entry point: creates QApplication and launches the main window

├── main_window.py       # Main PySide6 GUI window (~1,200 lines)

├── content_extractor.py # Content extraction module (URL / text / PDF)

├── rewriter.py          # AI rewriting core (prompt construction + Ollama calls)

├── worker.py            # Background thread management (QThread + Signal)

├── exporter.py          # File export (TXT / DOCX)

├── models.py            # Data models (RewriteConfig, ContentTask)

├── utils.py             # Utility functions (text cleanup, filename handling, etc.)

└── requirements.txt     # Python dependencies

## 🎯 Workflow
    Choose an input source — Select URL, text, or PDF in the left panel and provide the corresponding content.
    
    Configure rewriting parameters — Set parameters such as style, context, and audience in the top section.
    
    Click “Start Rewriting” — A background thread runs the extraction → AI rewriting process.
    
    View the result — Streaming output appears in real time in the right panel.
    
    Export the result — Save the rewritten content as TXT or DOCX.
    

## 🔧 Development
### Run and debug
python main.py

The application includes built-in console logging with DEBUG-level controls. See docs/DEBUG_LOG_GUIDE.md for detailed logging instructions.
