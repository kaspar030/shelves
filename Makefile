# Cluster-shelf pipeline.

MICROCAD ?= microcad
CONFIG    = .microcad.toml
BUILD_PY  = python3 scripts/build.py

.PHONY: all gen clean check fmt list help

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  %-10s %s\n",$$1,$$2}'

all:            ## Generate + export every shelf in shelves.toml
	$(BUILD_PY)

gen:            ## Only (re)generate gen/*.µcad from the manifest
	$(BUILD_PY) --gen-only

check: gen      ## Type-check every generated source
	@set -e; for f in gen/*.µcad; do \
	  echo "check $$f"; $(MICROCAD) -C $(CONFIG) check "$$f"; \
	done

fmt:            ## Format the library sources
	@for f in lib/*.µcad lib/devices/*.µcad; do $(MICROCAD) format "$$f" || true; done

list:           ## List exported STLs
	@ls -la build/*.stl 2>/dev/null || echo "nothing built yet — run 'make all'"

clean:          ## Remove generated sources and exported STLs
	rm -rf gen build
