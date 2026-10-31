# Cluster-shelf pipeline (µcad 0.6).

MUCAD    ?= mucad
BUILD_PY  = python3 scripts/build.py

.PHONY: all gen preview clean check fmt list help

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  %-10s %s\n",$$1,$$2}'

all:            ## Generate + export every shelf in shelves.toml
	$(BUILD_PY)

preview:        ## Like all, plus build/preview_*.stl assemblies
	$(BUILD_PY) --preview

gen:            ## Only (re)generate lib.mu (+ holder plans) from the manifest
	$(BUILD_PY) --gen-only

check: gen      ## Type-check the generated root (and the whole library)
	$(MUCAD) check lib.mu

fmt:            ## Format the library sources
	@for f in shelves.mu shelves/*.mu; do $(MUCAD) format "$$f" || true; done

list:           ## List exported STLs
	@ls -la build/*.stl 2>/dev/null || echo "nothing built yet — run 'make all'"

clean:          ## Remove the generated root and exported STLs
	rm -rf lib.mu build
