# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python project named "agent-communication" that uses Poetry for dependency management. The project is currently in early development (v0.1.0) with minimal structure.

## Development Environment

### Package Management
This project uses Poetry for dependency management. Poetry configuration is defined in `pyproject.toml`.

### Python Version
Requires Python >= 3.12, < 4.0

### Project Structure
```
agent-communication/
├── agent_communication/      # Main package directory (currently empty)
├── pyproject.toml            # Poetry configuration and project metadata
└── poetry.lock               # Locked dependencies
```

## Common Commands

### Install Dependencies
```bash
poetry install
```

### Add a New Dependency
```bash
poetry add <package-name>
```

### Add a Development Dependency
```bash
poetry add --group dev <package-name>
```

### Run Code in Poetry Environment
```bash
poetry run python <script.py>
```

### Activate Virtual Environment
```bash
poetry shell
```

## Architecture Notes

The project is currently in initial setup phase with:
- An empty `agent_communication` package directory awaiting implementation
- Poetry configured for dependency management
- No test structure or source files implemented yet

When developing in this codebase:
- Place Python modules inside the `agent_communication/` directory
- Follow standard Python package structure conventions
- Use Poetry for all dependency management operations
