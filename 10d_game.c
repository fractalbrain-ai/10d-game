#include "10d_game.h"

#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define FOV_SIZE 25
#define MAX_SATIETY_LEVEL 100.0F
#define MIN_SATIETY_LEVEL (-100.0F)
#define MAX_HYDRATION_LEVEL 100.0F
#define MIN_HYDRATION_LEVEL (-100.0F)

#define PATCH_SIZE 104
#define PATCH_STORAGE_SIZE 4096U
#define PATCH_DATA_SIZE 4056U
#define PATCH_LOOKUP_CAPACITY_INCREMENT 32U
#define TWO_PI 6.28318531F
#define MIN_SUN_SPATIAL_PERIOD 1.0F
#define WORLD_SEED_SALT 0x8f3f73b5U

typedef enum bean_flavor
{
    NO_BEAN = 0,
    SATIETY_BEAN = 1,
    HYDRATION_BEAN = 2,
    SALTY_BEAN = 3,
    BITTER_BEAN = 4,
} bean_flavor_t;

static const uint8_t BEAN_1_COLOR[4][2] = {
    {128, 128},
    {128, 255},
    {255, 128},
    {255, 255},
};

static const uint8_t BEAN_4_COLORS[16][2] = {
    {66, 66},
    {66, 129},
    {66, 192},
    {66, 255},
    {129, 66},
    {129, 129},
    {129, 192},
    {129, 255},
    {192, 66},
    {192, 129},
    {192, 192},
    {192, 255},
    {255, 66},
    {255, 129},
    {255, 192},
    {255, 255},
};

static const uint8_t BEAN_9_COLORS[36][2] = {
    {45, 45},  {45, 87},  {45, 129},  {45, 171},  {45, 213},  {45, 255},
    {87, 45},  {87, 87},  {87, 129},  {87, 171},  {87, 213},  {87, 255},
    {129, 45}, {129, 87}, {129, 129}, {129, 171}, {129, 213}, {129, 255},
    {171, 45}, {171, 87}, {171, 129}, {171, 171}, {171, 213}, {171, 255},
    {213, 45}, {213, 87}, {213, 129}, {213, 171}, {213, 213}, {213, 255},
    {255, 45}, {255, 87}, {255, 129}, {255, 171}, {255, 213}, {255, 255},
};

typedef struct pos
{
    int32_t x;
    int32_t y;
} pos_t;

typedef struct patch
{
    uint8_t *pixel;
    pos_t offset;
    uint32_t hash;
} patch_t;

typedef struct patch_lookup
{
    uint32_t *hashes;
    patch_t *patches;
    uint32_t size;
    uint32_t capacity;
} patch_lookup_t;

typedef struct patch_cache
{
    patch_t *bottom_left;
    patch_t *bottom_right;
    patch_t *top_left;
    patch_t *top_right;
} patch_cache_t;

typedef struct bean_color
{
    uint8_t r;
    uint8_t g;
} bean_color_t;

typedef struct bean_colors
{
    const uint8_t (*colors)[2];
    uint32_t n_colors;
    uint32_t stride;
    uint32_t offset;
} bean_colors_t;

typedef struct sun_cfg
{
    float wx;
    float wy;
    float wt;
    float cos_wx;
    float sin_wx;
    float cos_wy;
    float sin_wy;
    uint32_t cycle_duration;
} sun_cfg_t;

typedef struct fov
{
    uint8_t r[FOV_SIZE * FOV_SIZE];
    uint8_t g[FOV_SIZE * FOV_SIZE];
    uint8_t b[FOV_SIZE * FOV_SIZE];
} fov_t;

struct xdgame_state
{
    xdgame_config_t cfg;

    uint32_t world_seed;

    pos_t agent_pos;
    uint32_t t;

    float satiety;
    float hydration;
    bean_flavor_t inventory;

    uint32_t *pang_ticks;
    uint32_t pending_pangs;

    patch_lookup_t patch_lookup;
    patch_cache_t patch_cache;

    bean_colors_t bean_colors;

    sun_cfg_t sun_cfg;

    fov_t fov;
};

struct xdgame_map
{
    uint32_t width;
    uint32_t height;
    uint8_t *r;
    uint8_t *g;
    uint8_t *b;
};

[[nodiscard]] static uint32_t mix32(uint32_t x)
{
    x ^= x >> 16U;
    x *= (uint32_t)0x7feb352d;
    x ^= x >> 15U;
    x *= (uint32_t)0x846ca68b;
    x ^= x >> 16U;

    return x;
}

[[nodiscard]] static float to_unit_float(uint32_t random)
{
    return (float)(random >> 8U) / (float)(1U << 24U);
}

[[nodiscard]] static int32_t floor_div(int32_t x, int32_t divisor)
{
    assert(divisor > 0);
    return x / divisor - (int32_t)(x % divisor < 0);
}

[[nodiscard]] static uint32_t pack_grid_coords(int16_t x, int16_t y)
{
    uint32_t mask = 0xffff;
    uint32_t packed_x = (uint32_t)x & mask;
    uint32_t packed_y = (uint32_t)y & mask;

    return (packed_x << 16U) | packed_y;
}

[[nodiscard]] static uint32_t load_u24(const uint8_t *bytes)
{
    assert(bytes != NULL);

    return (uint32_t)bytes[0]        //
        | ((uint32_t)bytes[1] << 8U) //
        | ((uint32_t)bytes[2] << 16U);
}

static void store_u24(uint8_t *bytes, uint32_t value)
{
    assert(bytes != NULL);
    assert(value <= (uint32_t)0xffffff);

    bytes[0] = (uint8_t)value;
    bytes[1] = (uint8_t)(value >> 8U);
    bytes[2] = (uint8_t)(value >> 16U);
}

[[nodiscard]] static bean_flavor_t
get_flavor(const patch_t *patch, uint32_t x, uint32_t y)
{
    assert(patch != NULL);
    assert(patch->pixel != NULL);
    assert(x < PATCH_SIZE);
    assert(y < PATCH_SIZE);

    uint32_t pixel_idx = y * PATCH_SIZE + x;
    uint32_t group_idx = pixel_idx / 8U;
    uint32_t shift = (pixel_idx % 8U) * 3U;
    uint32_t byte_idx = group_idx * 3U;

    uint32_t packed = load_u24(&patch->pixel[byte_idx]);

    uint8_t encoded = (uint8_t)((packed >> shift) & 7U);
    assert(encoded <= 4);

    return (bean_flavor_t)encoded;
}

static void
set_flavor(patch_t *patch, uint32_t x, uint32_t y, bean_flavor_t flavor)
{
    assert(patch != NULL);
    assert(patch->pixel != NULL);
    assert(x < PATCH_SIZE);
    assert(y < PATCH_SIZE);
    assert((uint32_t)flavor <= 4);

    uint32_t pixel_idx = y * PATCH_SIZE + x;
    uint32_t group_idx = pixel_idx / 8U;
    uint32_t shift = (pixel_idx % 8U) * 3U;
    uint32_t byte_idx = group_idx * 3U;

    uint32_t packed = load_u24(&patch->pixel[byte_idx]);

    packed &= ~(7U << shift);
    packed |= (uint32_t)flavor << shift;

    store_u24(&patch->pixel[byte_idx], packed);
}

[[nodiscard]] static bean_colors_t
init_bean_colors(xdgame_bean_variants_t variant, uint32_t seed)
{
    bean_colors_t colors;

    uint32_t p;
    switch (variant)
    {
    case XDGAME_NO_BEAN_VARIANTS:
        colors.colors = BEAN_1_COLOR;
        colors.n_colors = 4;

        p = seed & 7U;
        colors.stride = 1U + 2U * (p >> 2U);
        colors.offset = p & 3U;
        break;

    case XDGAME_4_BEAN_VARIANTS:
        colors.colors = BEAN_4_COLORS;
        colors.n_colors = 16;

        p = seed & 127U;
        colors.stride = 1U + 2U * (p >> 4U);
        colors.offset = p & 15U;
        break;

    case XDGAME_9_BEAN_VARIANTS:
        colors.colors = BEAN_9_COLORS;
        colors.n_colors = 36;

        p = seed % 432U;
        colors.stride = 6U * ((p % 12U) >> 1U) + 1U + 4U * ((p % 12U) & 1U);
        colors.offset = p / 12U;
        break;
    }

    return colors;
}

static void fill_sun_channel(uint8_t *blue,
                             uint32_t width,
                             uint32_t height,
                             pos_t origin,
                             uint32_t t,
                             sun_cfg_t cfg)
{
    assert(blue != NULL);
    assert(width > 0);
    assert(height > 0);
    assert(cfg.cycle_duration > 0);

    float time_phase = cfg.wt * (float)(t % cfg.cycle_duration);

    float x = (float)origin.x;
    float x_phase = cfg.wx * x;
    if (fabsf(x_phase) > 0.5F * TWO_PI)
    {
        float x_period = TWO_PI / fabsf(cfg.wx);
        x = remainderf(x, x_period);
        x_phase = cfg.wx * x;
    }

    float y = (float)origin.y;
    float y_phase = cfg.wy * y;
    if (fabsf(y_phase) > 0.5F * TWO_PI)
    {
        float y_period = TWO_PI / fabsf(cfg.wy);
        y = remainderf(y, y_period);
        y_phase = cfg.wy * y;
    }

    float origin_phase = time_phase + x_phase + y_phase;
    float row_cos = cosf(origin_phase);
    float row_sin = sinf(origin_phase);

    size_t idx = 0;
    for (uint32_t i = 0; i < height; i++)
    {
        float pixel_cos = row_cos;
        float pixel_sin = row_sin;

        for (uint32_t j = 0; j < width; j++, idx++)
        {
            float lum = fmaxf(-1.0F, fminf(pixel_cos, 1.0F));
            blue[idx] = (uint8_t)(127.5F * (1.0F + lum));

            float old_cos = pixel_cos;
            pixel_cos = old_cos * cfg.cos_wx - pixel_sin * cfg.sin_wx;
            pixel_sin = pixel_sin * cfg.cos_wx + old_cos * cfg.sin_wx;
        }

        float old_cos = row_cos;
        row_cos = old_cos * cfg.cos_wy - row_sin * cfg.sin_wy;
        row_sin = row_sin * cfg.cos_wy + old_cos * cfg.sin_wy;
    }
}

[[nodiscard]] static bean_color_t get_bean_color(bean_flavor_t flavor,
                                                 bean_colors_t colors,
                                                 pos_t world_pos,
                                                 uint32_t biome_size,
                                                 uint32_t seed)
{
    assert(flavor >= 1 && flavor <= 4);
    assert(biome_size > 0 && biome_size <= INT32_MAX);

    int32_t divisor = (int32_t)biome_size;
    int32_t offset = divisor / 2;
    int32_t biome_x = floor_div(world_pos.x + offset, divisor);
    int32_t biome_y = floor_div(world_pos.y + offset, divisor);

    assert(biome_x >= INT16_MIN && biome_x <= INT16_MAX);
    assert(biome_y >= INT16_MIN && biome_y <= INT16_MAX);

    uint32_t biome_hash = pack_grid_coords((int16_t)biome_x, (int16_t)biome_y);

    uint32_t flavor_idx = (uint32_t)flavor - 1U;
    uint32_t n_variants = colors.n_colors / 4;

    uint32_t variant = mix32(seed ^ biome_hash ^ flavor_idx) % n_variants;
    uint32_t logical_idx = flavor_idx * n_variants + variant;

    uint32_t palette_idx =
        (colors.stride * logical_idx + colors.offset) % colors.n_colors;

    const uint8_t *color = colors.colors[palette_idx];

    return (bean_color_t){.r = color[0], .g = color[1]};
}

[[nodiscard]] static patch_t *get_cached_patch(const patch_cache_t *cache,
                                               pos_t world_pos)
{
    assert(cache != NULL);
    assert(cache->bottom_left != NULL);
    assert(cache->bottom_right != NULL);
    assert(cache->top_left != NULL);
    assert(cache->top_right != NULL);

    patch_t *patches[] = {
        cache->bottom_left,
        cache->bottom_right,
        cache->top_left,
        cache->top_right,
    };

    for (uint32_t i = 0; i < 4; i++)
    {
        if (world_pos.x >= patches[i]->offset.x
            && world_pos.y >= patches[i]->offset.y
            && world_pos.x < patches[i]->offset.x + PATCH_SIZE
            && world_pos.y < patches[i]->offset.y + PATCH_SIZE)
        {
            return patches[i];
        }
    }

    return NULL;
}

static void fill_fov(fov_t *fov,
                     pos_t agent_pos,
                     uint32_t t,
                     const patch_cache_t *patch_cache,
                     uint32_t seed,
                     bean_colors_t bean_colors,
                     uint32_t biome_size,
                     sun_cfg_t sun_cfg)
{
    assert(fov != NULL);
    assert(patch_cache != NULL);
    assert(sun_cfg.cycle_duration > 0);

    const int32_t radius = FOV_SIZE / 2;
    pos_t fov_origin = {
        .x = agent_pos.x - radius,
        .y = agent_pos.y - radius,
    };

    fill_sun_channel(fov->b, FOV_SIZE, FOV_SIZE, fov_origin, t, sun_cfg);

    for (uint32_t i = 0; i < FOV_SIZE; i++)
    {
        for (uint32_t j = 0; j < FOV_SIZE; j++)
        {
            uint32_t fov_idx = i * FOV_SIZE + j;

            pos_t world_pos = {
                .x = agent_pos.x + (int32_t)j - radius,
                .y = agent_pos.y + (int32_t)i - radius,
            };

            fov->r[fov_idx] = 0;
            fov->g[fov_idx] = 0;

            const patch_t *patch = get_cached_patch(patch_cache, world_pos);
            assert(patch != NULL);

            uint32_t local_x = (uint32_t)(world_pos.x - patch->offset.x);
            uint32_t local_y = (uint32_t)(world_pos.y - patch->offset.y);

            assert(local_x < PATCH_SIZE);
            assert(local_y < PATCH_SIZE);

            bean_flavor_t flavor = get_flavor(patch, local_x, local_y);
            if (flavor != NO_BEAN)
            {
                bean_color_t color = get_bean_color(
                    flavor, bean_colors, world_pos, biome_size, seed);

                fov->r[fov_idx] = color.r;
                fov->g[fov_idx] = color.g;
            }
        }
    }
}

[[nodiscard]] static uint32_t
find_hash_slot(const uint32_t *hashes, uint32_t size, uint32_t hash)
{
    uint32_t first = 0;
    uint32_t count = size;

    while (count > 0)
    {
        uint32_t step = count / 2U;
        uint32_t middle = first + step;

        if (hashes[middle] < hash)
        {
            first = middle + 1U;
            count -= step + 1U;
        }
        else
        {
            count = step;
        }
    }

    return first;
}

[[nodiscard]] static int
add_patch(patch_lookup_t *lookup, patch_t patch, uint32_t idx)
{
    assert(lookup != NULL);
    assert(patch.pixel != NULL);
    assert(lookup->size <= lookup->capacity);
    assert(idx <= lookup->size);
    assert(idx == 0 || lookup->hashes[idx - 1U] < patch.hash);
    assert(idx == lookup->size || patch.hash < lookup->hashes[idx]);

    if (lookup->size == lookup->capacity)
    {
        uint32_t new_capacity =
            lookup->capacity + PATCH_LOOKUP_CAPACITY_INCREMENT;

        size_t hashes_size = (size_t)new_capacity * sizeof(*lookup->hashes);
        size_t patches_size = (size_t)new_capacity * sizeof(*lookup->patches);

        uint32_t *new_hashes = malloc(hashes_size);
        if (new_hashes == NULL)
        {
            return 0;
        }

        patch_t *new_patches = malloc(patches_size);
        if (new_patches == NULL)
        {
            free(new_hashes);
            return 0;
        }

        if (idx > 0)
        {
            memcpy(
                new_hashes, lookup->hashes, (size_t)idx * sizeof(*new_hashes));
            memcpy(new_patches,
                   lookup->patches,
                   (size_t)idx * sizeof(*new_patches));
        }

        uint32_t tail_size = lookup->size - idx;
        if (tail_size > 0)
        {
            memcpy(&new_hashes[idx + 1U],
                   &lookup->hashes[idx],
                   (size_t)tail_size * sizeof(*new_hashes));
            memcpy(&new_patches[idx + 1U],
                   &lookup->patches[idx],
                   (size_t)tail_size * sizeof(*new_patches));
        }

        free(lookup->hashes);
        free(lookup->patches);

        lookup->hashes = new_hashes;
        lookup->patches = new_patches;
        lookup->capacity = new_capacity;
    }
    else
    {
        uint32_t tail_size = lookup->size - idx;
        if (tail_size > 0)
        {
            memmove(&lookup->hashes[idx + 1U],
                    &lookup->hashes[idx],
                    (size_t)tail_size * sizeof(*lookup->hashes));
            memmove(&lookup->patches[idx + 1U],
                    &lookup->patches[idx],
                    (size_t)tail_size * sizeof(*lookup->patches));
        }
    }

    lookup->hashes[idx] = patch.hash;
    lookup->patches[idx] = patch;
    lookup->size++;

    return 1;
}

[[nodiscard]] static int generate_patch(patch_t *patch,
                                        int16_t patch_x,
                                        int16_t patch_y,
                                        const xdgame_config_t *cfg,
                                        uint32_t seed)
{
    assert(patch != NULL);
    assert(cfg != NULL);

    uint8_t *pixel = aligned_alloc(PATCH_STORAGE_SIZE, PATCH_STORAGE_SIZE);
    if (pixel == NULL)
    {
        return 0;
    }

    memset(pixel, 0, PATCH_STORAGE_SIZE);

    *patch = (patch_t){
        .pixel = pixel,
        .offset =
            {
                .x = (int32_t)patch_x * PATCH_SIZE,
                .y = (int32_t)patch_y * PATCH_SIZE,
            },
        .hash = pack_grid_coords(patch_x, patch_y),
    };

    uint32_t patch_seed = mix32(seed ^ patch->hash);

    for (uint32_t local_y = 0; local_y < PATCH_SIZE; local_y++)
    {
        for (uint32_t local_x = 0; local_x < PATCH_SIZE; local_x++)
        {
            uint32_t pixel_idx = local_y * PATCH_SIZE + local_x;
            uint32_t random = mix32(patch_seed ^ pixel_idx);

            if (to_unit_float(random) < cfg->bean_density)
            {
                bean_flavor_t flavor = (bean_flavor_t)((random & 3U) + 1U);
                set_flavor(patch, local_x, local_y, flavor);
            }
        }
    }

    return 1;
}

[[nodiscard]] static patch_t *find_patch(patch_lookup_t *lookup,
                                         pos_t world_pos)
{
    int32_t patch_x = floor_div(world_pos.x, PATCH_SIZE);
    int32_t patch_y = floor_div(world_pos.y, PATCH_SIZE);

    assert(patch_x >= INT16_MIN && patch_x <= INT16_MAX);
    assert(patch_y >= INT16_MIN && patch_y <= INT16_MAX);

    uint32_t hash = pack_grid_coords((int16_t)patch_x, (int16_t)patch_y);
    uint32_t slot = find_hash_slot(lookup->hashes, lookup->size, hash);

    if (slot < lookup->size && lookup->hashes[slot] == hash)
    {
        return &lookup->patches[slot];
    }

    return NULL;
}

[[nodiscard]] static int ensure_patch(patch_lookup_t *lookup,
                                      pos_t world_pos,
                                      const xdgame_config_t *cfg,
                                      uint32_t seed)
{
    assert(lookup != NULL);
    assert(cfg != NULL);

    int32_t patch_x = floor_div(world_pos.x, PATCH_SIZE);
    int32_t patch_y = floor_div(world_pos.y, PATCH_SIZE);

    assert(patch_x >= INT16_MIN && patch_x <= INT16_MAX);
    assert(patch_y >= INT16_MIN && patch_y <= INT16_MAX);

    uint32_t hash = pack_grid_coords((int16_t)patch_x, (int16_t)patch_y);
    uint32_t slot = find_hash_slot(lookup->hashes, lookup->size, hash);
    if (slot < lookup->size && lookup->hashes[slot] == hash)
    {
        return 1;
    }

    patch_t patch;
    if (!generate_patch(&patch, (int16_t)patch_x, (int16_t)patch_y, cfg, seed))
    {
        return 0;
    }

    if (!add_patch(lookup, patch, slot))
    {
        free(patch.pixel);
        return 0;
    }

    return 1;
}

[[nodiscard]] static const patch_t *get_map_patch(xdgame_state_t *game,
                                                  patch_lookup_t *map_patches,
                                                  pos_t world_pos)
{
    const patch_t *patch = find_patch(&game->patch_lookup, world_pos);
    if (patch != NULL)
    {
        return patch;
    }

    if (!ensure_patch(map_patches, world_pos, &game->cfg, game->world_seed))
    {
        return NULL;
    }

    patch = find_patch(map_patches, world_pos);
    assert(patch != NULL);

    return patch;
}

static void free_patch_lookup(patch_lookup_t *lookup)
{
    assert(lookup != NULL);

    for (uint32_t i = 0; i < lookup->size; i++)
    {
        free(lookup->patches[i].pixel);
    }

    free(lookup->hashes);
    free(lookup->patches);
}

static void refresh_patch_cache(xdgame_state_t *game)
{
    assert(game != NULL);

    const int32_t radius = FOV_SIZE / 2;
    pos_t bottom_left = {
        .x = game->agent_pos.x - radius,
        .y = game->agent_pos.y - radius,
    };
    pos_t bottom_right = {
        .x = game->agent_pos.x + radius,
        .y = game->agent_pos.y - radius,
    };
    pos_t top_left = {
        .x = game->agent_pos.x - radius,
        .y = game->agent_pos.y + radius,
    };
    pos_t top_right = {
        .x = game->agent_pos.x + radius,
        .y = game->agent_pos.y + radius,
    };

    patch_cache_t *cache = &game->patch_cache;
    cache->bottom_left = find_patch(&game->patch_lookup, bottom_left);
    cache->bottom_right = find_patch(&game->patch_lookup, bottom_right);
    cache->top_left = find_patch(&game->patch_lookup, top_left);
    cache->top_right = find_patch(&game->patch_lookup, top_right);

    assert(cache->bottom_left != NULL);
    assert(cache->bottom_right != NULL);
    assert(cache->top_left != NULL);
    assert(cache->top_right != NULL);
}

static int set_agent_position(xdgame_state_t *game, int32_t x, int32_t y)
{
    assert(game != NULL);

    pos_t agent_pos = {.x = x, .y = y};
    const int32_t radius = FOV_SIZE / 2;
    if (agent_pos.x < INT32_MIN + radius    //
        || agent_pos.x > INT32_MAX - radius //
        || agent_pos.y < INT32_MIN + radius //
        || agent_pos.y > INT32_MAX - radius)
    {
        return 0;
    }

    const pos_t corners[] = {
        {.x = agent_pos.x - radius, .y = agent_pos.y - radius},
        {.x = agent_pos.x + radius, .y = agent_pos.y - radius},
        {.x = agent_pos.x - radius, .y = agent_pos.y + radius},
        {.x = agent_pos.x + radius, .y = agent_pos.y + radius},
    };

    int32_t min_patch_x = floor_div(corners[0].x, PATCH_SIZE);
    int32_t min_patch_y = floor_div(corners[0].y, PATCH_SIZE);
    int32_t max_patch_x = floor_div(corners[3].x, PATCH_SIZE);
    int32_t max_patch_y = floor_div(corners[3].y, PATCH_SIZE);

    if (min_patch_x < INT16_MIN    //
        || min_patch_y < INT16_MIN //
        || max_patch_x > INT16_MAX //
        || max_patch_y > INT16_MAX)
    {
        return 0;
    }

    int32_t biome_size = (int32_t)game->cfg.bean_biome_size;
    int32_t biome_offset = biome_size / 2;
    int32_t min_biome_x = floor_div(corners[0].x + biome_offset, biome_size);
    int32_t min_biome_y = floor_div(corners[0].y + biome_offset, biome_size);
    int32_t max_biome_x = floor_div(corners[3].x + biome_offset, biome_size);
    int32_t max_biome_y = floor_div(corners[3].y + biome_offset, biome_size);

    if (min_biome_x < INT16_MIN    //
        || min_biome_y < INT16_MIN //
        || max_biome_x > INT16_MAX //
        || max_biome_y > INT16_MAX)
    {
        return 0;
    }

    patch_cache_t *cache = &game->patch_cache;
    int cache_ready = cache->bottom_left != NULL //
        && cache->bottom_right != NULL           //
        && cache->top_left != NULL               //
        && cache->top_right != NULL;

    if (cache_ready)
    {
        int fov_is_cached = 1;
        for (uint32_t i = 0; i < 4; i++)
        {
            if (get_cached_patch(cache, corners[i]) == NULL)
            {
                fov_is_cached = 0;
                break;
            }
        }

        if (fov_is_cached)
        {
            game->agent_pos = agent_pos;
            return 1;
        }
    }

    for (uint32_t i = 0; i < 4; i++)
    {
        if (!ensure_patch(
                &game->patch_lookup, corners[i], &game->cfg, game->world_seed))
        {
            if (cache_ready)
            {
                refresh_patch_cache(game);
            }
            return 0;
        }
    }

    game->agent_pos = agent_pos;

    refresh_patch_cache(game);

    return 1;
}

xdgame_config_t *xdgame_default_config(void)
{
    xdgame_config_t *cfg = malloc(sizeof(*cfg));
    if (cfg == NULL)
    {
        return NULL;
    }

    *cfg = (xdgame_config_t){
        .bean_variants = XDGAME_4_BEAN_VARIANTS,
        .bean_density = 0.01F,
        .bean_biome_size = 1000,

        .needs_decay = 0.1F,

        .satiety_bean_satiety_gain = 3.F,
        .hydration_bean_hydration_gain = 10.F,
        .salty_bean_satiety_gain = 10.F,
        .salty_bean_hydration_loss = 10.F,
        .salty_bean_delay = 10,
        .bitter_bean_penalty = 10.F,

        .sun_spatial_period = 200.F,
        .sun_cycle_duration = 400,
        .sun_reward = 1.F,
    };

    return cfg;
}

void xdgame_free_config(xdgame_config_t *cfg)
{
    free(cfg);
}

xdgame_state_t *xdgame_new_game(uint32_t seed, const xdgame_config_t *cfg)
{
    if (cfg == NULL
        || (cfg->bean_variants != XDGAME_NO_BEAN_VARIANTS
            && cfg->bean_variants != XDGAME_4_BEAN_VARIANTS
            && cfg->bean_variants != XDGAME_9_BEAN_VARIANTS)
        || !isfinite(cfg->bean_density)                     //
        || cfg->bean_density < 0.0F                         //
        || cfg->bean_density > 1.0F                         //
        || cfg->bean_biome_size == 0                        //
        || cfg->bean_biome_size > INT32_MAX                 //
        || !isfinite(cfg->needs_decay)                      //
        || !isfinite(cfg->satiety_bean_satiety_gain)        //
        || !isfinite(cfg->hydration_bean_hydration_gain)    //
        || !isfinite(cfg->salty_bean_satiety_gain)          //
        || !isfinite(cfg->salty_bean_hydration_loss)        //
        || !isfinite(cfg->bitter_bean_penalty)              //
        || !isfinite(cfg->sun_spatial_period)               //
        || cfg->sun_spatial_period < MIN_SUN_SPATIAL_PERIOD //
        || cfg->sun_cycle_duration == 0                     //
        || !isfinite(cfg->sun_reward))                      //
    {
        return NULL;
    }

    xdgame_state_t *game = malloc(sizeof(*game));
    if (game == NULL)
    {
        return NULL;
    }

    uint32_t world_seed = mix32(seed ^ WORLD_SEED_SALT);
    float phi = TWO_PI * to_unit_float(world_seed);
    float wx = TWO_PI / cfg->sun_spatial_period * cosf(phi);
    float wy = TWO_PI / cfg->sun_spatial_period * sinf(phi);
    float wt = TWO_PI / (float)cfg->sun_cycle_duration;

    *game = (xdgame_state_t){
        .cfg = *cfg,
        .world_seed = world_seed,
        .agent_pos = {.x = 0, .y = 0},
        .t = 0,
        .satiety = MAX_SATIETY_LEVEL,
        .hydration = MAX_HYDRATION_LEVEL,
        .inventory = NO_BEAN,
        .pang_ticks = NULL,
        .pending_pangs = 0,
        .patch_lookup =
            {
                .hashes = NULL,
                .patches = NULL,
                .size = 0,
                .capacity = 0,
            },
        .patch_cache =
            {
                .bottom_left = NULL,
                .bottom_right = NULL,
                .top_left = NULL,
                .top_right = NULL,
            },
        .bean_colors = init_bean_colors(cfg->bean_variants, world_seed),
        .sun_cfg =
            {
                .wx = wx,
                .wy = wy,
                .wt = wt,
                .cos_wx = cosf(wx),
                .sin_wx = sinf(wx),
                .cos_wy = cosf(wy),
                .sin_wy = sinf(wy),
                .cycle_duration = cfg->sun_cycle_duration,
            },
        .fov =
            {
                .r = {0},
                .g = {0},
                .b = {0},
            },
    };

    if (!xdgame_set_agent(game, game->agent_pos.x, game->agent_pos.y))
    {
        free_patch_lookup(&game->patch_lookup);
        free(game);
        return NULL;
    }

    return game;
}

void xdgame_free_game(xdgame_state_t *game)
{
    if (game != NULL)
    {
        free(game->pang_ticks);
        free_patch_lookup(&game->patch_lookup);
        free(game);
    }
}

xdgame_map_t *xdgame_generate_map(xdgame_state_t *game,
                                  int32_t center_x,
                                  int32_t center_y,
                                  uint32_t width,
                                  uint32_t height,
                                  uint32_t t)
{
    if (game == NULL   //
        || width == 0  //
        || height == 0 //
        || (size_t)width > SIZE_MAX / (size_t)height)
    {
        return NULL;
    }

    int32_t left = (int32_t)(width / 2U);
    int32_t right = (int32_t)(width - width / 2U - 1U);
    int32_t bottom = (int32_t)(height / 2U);
    int32_t top = (int32_t)(height - height / 2U - 1U);

    if (center_x < INT32_MIN + left      //
        || center_x > INT32_MAX - right  //
        || center_y < INT32_MIN + bottom //
        || center_y > INT32_MAX - top)
    {
        return NULL;
    }

    int32_t start_x = center_x - left;
    int32_t end_x = center_x + right;
    int32_t start_y = center_y - bottom;
    int32_t end_y = center_y + top;

    int32_t min_patch_x = floor_div(start_x, PATCH_SIZE);
    int32_t max_patch_x = floor_div(end_x, PATCH_SIZE);
    int32_t min_patch_y = floor_div(start_y, PATCH_SIZE);
    int32_t max_patch_y = floor_div(end_y, PATCH_SIZE);

    if (min_patch_x < INT16_MIN    //
        || max_patch_x > INT16_MAX //
        || min_patch_y < INT16_MIN //
        || max_patch_y > INT16_MAX)
    {
        return NULL;
    }

    int32_t biome_size = (int32_t)game->cfg.bean_biome_size;
    int32_t biome_offset = biome_size / 2;
    int32_t min_biome_x = floor_div(start_x + biome_offset, biome_size);
    int32_t max_biome_x = floor_div(end_x + biome_offset, biome_size);
    int32_t min_biome_y = floor_div(start_y + biome_offset, biome_size);
    int32_t max_biome_y = floor_div(end_y + biome_offset, biome_size);

    if (min_biome_x < INT16_MIN    //
        || max_biome_x > INT16_MAX //
        || min_biome_y < INT16_MIN //
        || max_biome_y > INT16_MAX)
    {
        return NULL;
    }

    size_t pixel_count = (size_t)width * (size_t)height;

    xdgame_map_t *map = malloc(sizeof(*map));
    if (map == NULL)
    {
        return NULL;
    }

    *map = (xdgame_map_t){
        .width = width,
        .height = height,
        .r = NULL,
        .g = NULL,
        .b = NULL,
    };

    map->r = malloc(pixel_count);
    map->g = malloc(pixel_count);
    map->b = malloc(pixel_count);
    if (map->r == NULL || map->g == NULL || map->b == NULL)
    {
        xdgame_free_map(map);
        return NULL;
    }

    patch_lookup_t map_patches = {
        .hashes = NULL,
        .patches = NULL,
        .size = 0,
        .capacity = 0,
    };

    pos_t map_origin = {.x = start_x, .y = start_y};
    fill_sun_channel(
        map->b, map->width, map->height, map_origin, t, game->sun_cfg);

    size_t map_idx = 0;
    int32_t world_y = start_y;

    for (uint32_t i = 0; i < height; i++, world_y++)
    {
        const patch_t *patch = NULL;
        int32_t world_x = start_x;

        for (uint32_t j = 0; j < width; j++, world_x++, map_idx++)
        {
            pos_t world_pos = {.x = world_x, .y = world_y};
            if (patch == NULL || world_x >= patch->offset.x + PATCH_SIZE)
            {
                patch = get_map_patch(game, &map_patches, world_pos);
                if (patch == NULL)
                {
                    free_patch_lookup(&map_patches);
                    xdgame_free_map(map);
                    return NULL;
                }
            }

            uint32_t local_x = (uint32_t)(world_x - patch->offset.x);
            uint32_t local_y = (uint32_t)(world_y - patch->offset.y);
            assert(local_x < PATCH_SIZE);
            assert(local_y < PATCH_SIZE);

            map->r[map_idx] = 0;
            map->g[map_idx] = 0;

            bean_flavor_t flavor = get_flavor(patch, local_x, local_y);
            if (flavor != NO_BEAN)
            {
                bean_color_t color = get_bean_color(flavor,
                                                    game->bean_colors,
                                                    world_pos,
                                                    game->cfg.bean_biome_size,
                                                    game->world_seed);
                map->r[map_idx] = color.r;
                map->g[map_idx] = color.g;
            }
        }
    }

    free_patch_lookup(&map_patches);

    return map;
}

void xdgame_free_map(xdgame_map_t *map)
{
    if (map != NULL)
    {
        free(map->r);
        free(map->g);
        free(map->b);
        free(map);
    }
}

const uint8_t *xdgame_get_map_r(const xdgame_map_t *map)
{
    return map->r;
}

const uint8_t *xdgame_get_map_g(const xdgame_map_t *map)
{
    return map->g;
}

const uint8_t *xdgame_get_map_b(const xdgame_map_t *map)
{
    return map->b;
}

uint32_t xdgame_get_map_width(const xdgame_map_t *map)
{
    return map->width;
}

uint32_t xdgame_get_map_height(const xdgame_map_t *map)
{
    return map->height;
}

int xdgame_set_agent(xdgame_state_t *game, int32_t x, int32_t y)
{
    if (!set_agent_position(game, x, y))
    {
        return 0;
    }

    fill_fov(&game->fov,
             game->agent_pos,
             game->t,
             &game->patch_cache,
             game->world_seed,
             game->bean_colors,
             game->cfg.bean_biome_size,
             game->sun_cfg);

    return 1;
}

[[nodiscard]] static float eat_bean(xdgame_state_t *game,
                                    patch_t *patch,
                                    uint32_t local_x,
                                    uint32_t local_y,
                                    bean_flavor_t flavor)
{
    assert(game != NULL);
    assert(patch != NULL);
    assert(local_x < PATCH_SIZE);
    assert(local_y < PATCH_SIZE);
    assert((uint32_t)flavor <= 4);

    if (flavor == SALTY_BEAN && game->cfg.salty_bean_delay > 0)
    {
        uint32_t new_size = game->pending_pangs + 1U;
        uint32_t *new_ticks = realloc(
            game->pang_ticks, (size_t)new_size * sizeof(*game->pang_ticks));
        if (new_ticks == NULL)
        {
            return 0.0F;
        }

        game->pang_ticks = new_ticks;
        game->pang_ticks[game->pending_pangs] =
            game->t + game->cfg.salty_bean_delay;
        game->pending_pangs = new_size;
    }

    float reward = 0.0F;
    switch (flavor)
    {
    case NO_BEAN:
        return reward;
    case SATIETY_BEAN:
        game->satiety = fmaxf( //
            fminf(game->satiety + game->cfg.satiety_bean_satiety_gain,
                  MAX_SATIETY_LEVEL),
            MIN_SATIETY_LEVEL);
        break;
    case HYDRATION_BEAN:
        game->hydration = fmaxf( //
            fminf(game->hydration + game->cfg.hydration_bean_hydration_gain,
                  MAX_HYDRATION_LEVEL),
            MIN_HYDRATION_LEVEL);
        break;
    case SALTY_BEAN:
        game->satiety =
            fmaxf(fminf(game->satiety + game->cfg.salty_bean_satiety_gain,
                        MAX_SATIETY_LEVEL),
                  MIN_SATIETY_LEVEL);
        if (game->cfg.salty_bean_delay == 0)
        {
            game->hydration =
                fmaxf(game->hydration - game->cfg.salty_bean_hydration_loss,
                      MIN_HYDRATION_LEVEL);
        }
        break;
    case BITTER_BEAN:
        reward = -game->cfg.bitter_bean_penalty;
        break;
    }

    set_flavor(patch, local_x, local_y, NO_BEAN);

    return reward;
}

float xdgame_tick(xdgame_state_t *game, xdgame_action_t action)
{
    assert(game != NULL);

    {
        uint32_t n = 0;
        while (n < game->pending_pangs && game->pang_ticks[n] == game->t)
        {
            n++;
        }

        if (n > 0)
        {
            game->hydration =
                fmaxf(game->hydration
                          - (float)n * game->cfg.salty_bean_hydration_loss,
                      MIN_HYDRATION_LEVEL);
            game->pending_pangs -= n;
            memmove(game->pang_ticks,
                    &game->pang_ticks[n],
                    (size_t)game->pending_pangs * sizeof(*game->pang_ticks));
        }
    }

    game->satiety =
        fmaxf(fminf(game->satiety - game->cfg.needs_decay, MAX_SATIETY_LEVEL),
              MIN_SATIETY_LEVEL);
    game->hydration = fmaxf(
        fminf(game->hydration - game->cfg.needs_decay, MAX_HYDRATION_LEVEL),
        MIN_HYDRATION_LEVEL);

    float reward = 0.0F;

    patch_t *patch = NULL;

    uint32_t local_x = 0;
    uint32_t local_y = 0;

    bean_flavor_t flavor = NO_BEAN;

    if (action == XDGAME_EAT_BEAN       //
        || action == XDGAME_PICKUP_BEAN //
        || action == XDGAME_DROP_BEAN)
    {
        patch = get_cached_patch(&game->patch_cache, game->agent_pos);
        assert(patch != NULL);

        local_x = (uint32_t)(game->agent_pos.x - patch->offset.x);
        local_y = (uint32_t)(game->agent_pos.y - patch->offset.y);
        assert(local_x < PATCH_SIZE);
        assert(local_y < PATCH_SIZE);

        flavor = get_flavor(patch, local_x, local_y);
    }

    switch (action)
    {
    case XDGAME_MOVE_NORTH:
        set_agent_position(game, game->agent_pos.x, game->agent_pos.y + 1);
        break;
    case XDGAME_MOVE_EAST:
        set_agent_position(game, game->agent_pos.x + 1, game->agent_pos.y);
        break;
    case XDGAME_MOVE_SOUTH:
        set_agent_position(game, game->agent_pos.x, game->agent_pos.y - 1);
        break;
    case XDGAME_MOVE_WEST:
        set_agent_position(game, game->agent_pos.x - 1, game->agent_pos.y);
        break;
    case XDGAME_EAT_BEAN:
        reward += eat_bean(game, patch, local_x, local_y, flavor);
        break;
    case XDGAME_PICKUP_BEAN:
        if (game->inventory == NO_BEAN && flavor != NO_BEAN)
        {
            game->inventory = flavor;
            set_flavor(patch, local_x, local_y, NO_BEAN);
        }
        break;
    case XDGAME_DROP_BEAN:
        if (game->inventory != NO_BEAN && flavor == NO_BEAN)
        {
            set_flavor(patch, local_x, local_y, game->inventory);
            game->inventory = NO_BEAN;
        }
        break;
    default:
        break;
    }

    reward += fminf(game->satiety, 0.0F) + fminf(game->hydration, 0.0F);

    fill_fov(&game->fov,
             game->agent_pos,
             game->t,
             &game->patch_cache,
             game->world_seed,
             game->bean_colors,
             game->cfg.bean_biome_size,
             game->sun_cfg);

    uint32_t center = (FOV_SIZE / 2U) * FOV_SIZE + FOV_SIZE / 2U;
    reward += game->cfg.sun_reward * (float)game->fov.b[center] / 255.F;

    game->t++;

    return reward;
}

float xdgame_get_satiety_level(const xdgame_state_t *game)
{
    return game->satiety;
}

float xdgame_get_hydration_level(const xdgame_state_t *game)
{
    return game->hydration;
}

uint32_t xdgame_get_inventory_count(const xdgame_state_t *game)
{
    return (uint32_t)(game->inventory != NO_BEAN);
}

const uint8_t *xdgame_get_fov_r(const xdgame_state_t *game)
{
    return game->fov.r;
}

const uint8_t *xdgame_get_fov_g(const xdgame_state_t *game)
{
    return game->fov.g;
}

const uint8_t *xdgame_get_fov_b(const xdgame_state_t *game)
{
    return game->fov.b;
}

uint32_t xdgame_fov_size(const xdgame_config_t *cfg)
{
    (void)cfg;

    return FOV_SIZE;
}
