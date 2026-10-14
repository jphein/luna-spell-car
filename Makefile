# Luna's Spell Car — development cycle
#   make dev        live-reload server at http://localhost:8000 (also on your LAN for the tablet's browser)
#   make test       static checks + browser smoke tests (Playwright/Chromium)
#   make apk        build build/luna-spell-car.apk at the version in VERSION
#   make install    adb install -r onto a connected tablet (USB or `adb connect <ip>:5555`)
#   make server     run the Spell Car server (Azure) from server/.env
#   make release    bump version (PART=patch|minor|major), roll CHANGELOG, test, build, commit, tag
VERSION := $(shell cat VERSION)
PART ?= patch
PY ?= python3

.PHONY: build dev check test apk install release clean hooks server
build:
	$(PY) web/build.py
dev:
	$(PY) tools/dev.py
check: build
	$(PY) tools/check.py
test: check
	$(PY) tests/test_server.py
	$(PY) tests/smoke.py
apk:
	./build_apk.sh
install: apk
	adb install -r build/luna-spell-car.apk
release:
	$(PY) tools/release.py $(PART)
	$(MAKE) test apk
	git add -A && git commit -qm "Release v$$(cat VERSION)" && git tag "v$$(cat VERSION)"
	@echo "Released v$$(cat VERSION) -> build/luna-spell-car.apk"
hooks:
	printf '#!/bin/sh\nmake -s check\n' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
clean:
	rm -rf build dist android/assets
server:
	$(PY) server/spellcar_server.py
