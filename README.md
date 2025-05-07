# stm - Source to Markdown

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A command-line utility that intelligently converts your codebase into a single Markdown file, perfectly formatted for providing context to Large Language Models (LLMs).

## Overview

`stm` helps you prepare your code for LLM interactions by:

- Converting multiple source files into a well-formatted Markdown document
- Respecting `.gitignore` rules to exclude irrelevant files
- Detecting binary files and excluding them from output
- Automatically selecting appropriate language syntax highlighting
- Supporting glob patterns to easily specify target files

This is particularly useful when you need to provide code context to AI assistants like ChatGPT, Claude, or GitHub Copilot.

## Installation

You need [uv](https://github.com/astral-sh/uv) installed for the simplest installation:

```bash
uv tool install git+https://github.com/blasferna/stm.git
```

## Usage

```
stm [paths...] [-o OUTPUT] [--project-root PROJECT_ROOT] [--no-gitignore] [--verbose]
```

### Basic Examples

```bash
# Convert entire current directory to stdout
stm

# Convert specific directory to a file
stm src -o context.md

# Convert multiple specific files
stm src/main.py tests/test_utils.py -o llm_context.md

# Use glob patterns to select files
stm "src/**/*.py" "tests/unit/**/*.py" -o context.md

# Pipe output to clipboard (macOS)
stm "src/**/*.py" | pbcopy

# Pipe output to clipboard (Linux with xclip)
stm "src/**/*.py" | xclip -selection clipboard

# Pipe output to clipboard (Windows)
stm "src/**/*.py" | clip
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `paths` | Paths to process (files, directories, or glob patterns like `src/**/*.py`). Default: current directory `.` |
| `-o, --output OUTPUT` | Output Markdown file. If not specified, prints to stdout. |
| `--project-root PROJECT_ROOT` | Specify the project root directory. `.gitignore` files are processed relative to this. Default: current working directory. |
| `--no-gitignore` | Disable `.gitignore` file processing. |
| `--verbose, -v` | Print verbose output, like skipped files. |

## Features

- **Smart File Filtering**: Automatically excludes binary files, respects `.gitignore` rules
- **Language Detection**: Automatically adds language identifiers for syntax highlighting
- **Path Preservation**: Maintains original file paths in the output for context
- **Cross-Platform**: Works consistently across operating systems
- **Flexible Input**: Accept individual files, directories, or glob patterns

## Use Cases

- Prepare codebase snapshots for LLM conversations
- Generate documentation-ready code listings
- Create shareable code overviews
- Prepare code context for AI pair programming

## License

MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Blas Isaias Fernández ([@blasferna](https://github.com/blasferna))
