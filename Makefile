ifeq ($(OS),Windows_NT)
VENV_BIN = .venv/Scripts
EXE = .exe
else
VENV_BIN = .venv/bin
EXE =
endif

PYTHON = $(VENV_BIN)/python$(EXE)
PIP = $(VENV_BIN)/pip$(EXE)
PYTEST = $(VENV_BIN)/pytest$(EXE)
RUFF = $(VENV_BIN)/ruff$(EXE)
MYPY = $(VENV_BIN)/mypy$(EXE)

install:
	$(PIP) install -e .[dev]

test:
	$(PYTEST)

lint:
	$(RUFF) check .

mypy:
	$(MYPY) src tests

format:
	$(RUFF) format --check .
