FILES := 10d_game.h 10d_game.c
EMCC := 3rd-party/emsdk/upstream/emscripten/emcc
BUILD_DIR := build
WASM := $(BUILD_DIR)/10d_game.wasm
HTML_SOURCE := bindings/browser/10d_game.html
HTML := $(BUILD_DIR)/10d_game.html
WASM_EXPORTS := [\
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
    "_xdgame_get_fov_r",\
    "_xdgame_get_fov_g",\
    "_xdgame_get_fov_b",\
    "_xdgame_fov_size"\
]

.PHONY: all check clean format html wasm

all: wasm

check:
	clang-format --dry-run --Werror $(FILES)
	clang-tidy $(FILES) -- -xc -std=c23

clean:
	rm -rf $(BUILD_DIR)

format:
	clang-format -i $(FILES)

wasm: $(WASM)

html: $(HTML)

$(HTML): $(HTML_SOURCE) $(WASM) | $(BUILD_DIR)
	sed "s|@WASM_BASE64@|$$(base64 < $(WASM) | tr -d '\n')|" $< > $@

$(WASM): 10d_game.c 10d_game.h | $(BUILD_DIR)
	$(EMCC) 10d_game.c -std=c23 -O3 -DNDEBUG --no-entry \
		-sPURE_WASI=1 -sFILESYSTEM=0 \
		-sEXPORTED_FUNCTIONS='$(WASM_EXPORTS)' -o $@

$(BUILD_DIR):
	mkdir -p $@
