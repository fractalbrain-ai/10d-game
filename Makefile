ENGINE_FILES := 10d_game.h 10d_game.c
VERSION_SOURCE := docs/print_version.c
C_FILES := $(ENGINE_FILES) $(VERSION_SOURCE)
EMCC := 3rd-party/emsdk/upstream/emscripten/emcc
HOST_CC ?= cc
BUILD_DIR := build
WASM := $(BUILD_DIR)/10d_game.wasm
HTML_SOURCE := bindings/browser/10d_game.html
HTML := $(BUILD_DIR)/10d_game.html
VERSION_TOOL := $(BUILD_DIR)/xdgame-version
WASM_EXPORTS := [\
    "_xdgame_version_major",\
    "_xdgame_version_minor",\
    "_xdgame_version_patch",\
    "_xdgame_default_config",\
    "_xdgame_free_config",\
    "_xdgame_new_game",\
    "_xdgame_free_game",\
    "_xdgame_generate_map",\
    "_xdgame_free_map",\
    "_xdgame_get_map_r",\
    "_xdgame_get_map_g",\
    "_xdgame_get_map_b",\
    "_xdgame_get_map_width",\
    "_xdgame_get_map_height",\
    "_xdgame_set_agent",\
    "_xdgame_tick",\
    "_xdgame_get_satiety_level",\
    "_xdgame_get_hydration_level",\
    "_xdgame_get_inventory_count",\
    "_xdgame_reveal_last_eaten_flavor",\
    "_xdgame_get_fov_r",\
    "_xdgame_get_fov_g",\
    "_xdgame_get_fov_b",\
    "_xdgame_fov_size"\
]

.PHONY: all check clean docs format html wasm

all: wasm

check:
	clang-format --dry-run --Werror $(C_FILES)
	clang-tidy $(C_FILES) -- -xc -std=c23 -I.

clean:
	rm -rf $(BUILD_DIR)

docs: $(VERSION_TOOL)
	XDGAME_VERSION="$$(./$(VERSION_TOOL))" $(MAKE) -C docs html

format:
	clang-format -i $(C_FILES)

wasm: $(WASM)

html: $(HTML)

$(HTML): $(HTML_SOURCE) $(WASM) | $(BUILD_DIR)
	sed "s|@WASM_BASE64@|$$(base64 < $(WASM) | tr -d '\n')|" $< > $@

$(WASM): $(ENGINE_FILES) | $(BUILD_DIR)
	$(EMCC) 10d_game.c -std=c23 -O3 -DNDEBUG --no-entry \
		-sPURE_WASI=1 -sFILESYSTEM=0 \
		-sEXPORTED_FUNCTIONS='$(WASM_EXPORTS)' -o $@

$(VERSION_TOOL): $(VERSION_SOURCE) $(ENGINE_FILES) | $(BUILD_DIR)
	$(HOST_CC) -I. -std=c23 $(VERSION_SOURCE) 10d_game.c -lm -o $@

$(BUILD_DIR):
	mkdir -p $@
