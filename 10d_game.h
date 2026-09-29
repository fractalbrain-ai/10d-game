#ifndef XDGAME_H
#define XDGAME_H

#include <stdint.h>

#ifdef __cplusplus
extern "C"
{
#endif

/**
 * \file 10d_game.h
 * \anchor xdgame_api
 * \brief 10d_game engine API.
 *
 * This header defines a deterministic procedural world containing four bean
 * flavors and an agent that observes a square field of view. Start with a
 * configuration returned by ::xdgame_default_config(), adjust its public
 * fields as needed, and pass it to ::xdgame_new_game(). The game copies the
 * configuration, so the original can then be released with
 * ::xdgame_free_config().
 *
 * The world is procedurally generated on demand and behaves like an infinite
 * world in ordinary use—with one practical asterisk: the current patch and
 * biome coordinates are 16-bit. This limits the span along each axis to at
 * most 6,815,744 cells, and a small \c bean_biome_size can reduce it further.
 * See ::xdgame_config_t for details.
 *
 * Advance the agent with ::xdgame_tick(). Query its current needs and carried
 * bean with ::xdgame_get_satiety_level(), ::xdgame_get_hydration_level(), and
 * ::xdgame_get_inventory_count(). Inspect the resulting field of view through
 * ::xdgame_get_fov_r(), ::xdgame_get_fov_g(), and ::xdgame_get_fov_b(). Its
 * side length is returned by ::xdgame_fov_size(). The agent occupies the center
 * cell but is not drawn in any channel; callers that visualize the field of
 * view must add their own marker at the center.
 *
 * For a larger plot of the world, create an independent RGB snapshot with
 * ::xdgame_generate_map(), access its channels and dimensions with the
 * corresponding map getters, and release it with ::xdgame_free_map(). Release
 * the game itself with ::xdgame_free_game() when it is no longer needed.
 *
 * Both fields of view and maps are RGB images represented by three separate
 * byte arrays: an R(ed), G(reen), and B(lue) color channel. The channels are
 * accessed through the corresponding functions ending in \c _r, \c _g, and
 * \c _b. Values at the same array index in the three channels together form
 * one RGB pixel.
 *
 * Each channel uses row-major layout. Its first element represents the
 * lower-left world position. Consecutive elements move from left to right
 * along x; after one image-width of elements, the next row begins one cell
 * higher along y. Relative image coordinates \c (x,y) therefore use the array
 * index \c y*width+x.
 */

/**
 * \brief Number of possible color variants for each bean flavor.
 */
typedef enum xdgame_bean_variants
{
    XDGAME_NO_BEAN_VARIANTS, /**< One color per flavor. */
    XDGAME_4_BEAN_VARIANTS,  /**< Four colors per flavor. */
    XDGAME_9_BEAN_VARIANTS,  /**< Nine colors per flavor. */
} xdgame_bean_variants_t;

/**
 * \brief Parameters used to initialize a game.
 *
 * A bean's flavor describes its gameplay effect, independently of the color
 * used to draw it:
 *
 * - A satiety bean changes the agent's satiety immediately.
 * - A hydration bean changes the agent's hydration immediately.
 * - A salty bean changes satiety immediately and hydration after a configured
 *   delay.
 * - A bitter bean applies an immediate reward penalty.
 *
 * Satiety and hydration are measured in level points. Both start at 100 and
 * change every tick according to \c needs_decay. A level below zero contributes
 * that negative value to the tick reward.
 *
 * The \c bean_variants member must contain one of the declared
 * ::xdgame_bean_variants_t values. Every floating-point member must be finite;
 * additional requirements are documented with the corresponding member.
 */
typedef struct xdgame_config
{
    /**
     * Number of possible colors for each flavor.
     *
     * A flavor may be drawn with different colors in different biomes, but
     * within one game a particular color always identifies the same flavor.
     * This setting changes only that visual variety, not bean effects or
     * generation probability. The value must be one of the declared
     * ::xdgame_bean_variants_t values.
     */
    xdgame_bean_variants_t bean_variants;

    /**
     * Probability of placing a bean on a generated world cell.
     *
     * The value is a dimensionless probability in [0, 1]. For example, 0.01
     * produces one bean per 100 cells on average. If a bean is placed, each of
     * the four flavors is selected with equal probability.
     */
    float bean_density;

    /**
     * Bean-color biome side length in [1, \c INT32_MAX].
     *
     * The world is divided into square color biomes with this width and height,
     * measured in cells. Within a biome, each flavor has one consistent color;
     * crossing into another biome may change those colors. Biome size does not
     * affect whether a bean is placed or which flavor it has.
     *
     * Biomes are offset by half their side length so that world position (0, 0)
     * lies in the middle of a biome. Because biome coordinates are currently
     * 16-bit, this value also limits the practical world span along each axis
     * to about 65,536 times \c bean_biome_size cells. The independent
     * patch-coordinate limit caps that span at 6,815,744 cells.
     */
    uint32_t bean_biome_size;

    /**
     * Value subtracted from satiety and hydration every tick, in level points.
     *
     * A positive value decreases both levels; a negative value increases them.
     */
    float needs_decay;

    /**
     * Immediate satiety change from eating a satiety bean, in level points.
     *
     * A positive value restores satiety; a negative value reduces it.
     */
    float satiety_bean_satiety_gain;

    /**
     * Immediate hydration change from eating a hydration bean, in level
     * points.
     *
     * A positive value restores hydration; a negative value reduces it.
     */
    float hydration_bean_hydration_gain;

    /**
     * Immediate satiety change from eating a salty bean, in level points.
     *
     * A positive value restores satiety; a negative value reduces it.
     */
    float salty_bean_satiety_gain;

    /**
     * Hydration loss caused by eating a salty bean, in level points.
     *
     * This value is subtracted from hydration after \c salty_bean_delay. A
     * positive value therefore reduces hydration, while a negative value
     * increases it.
     */
    float salty_bean_hydration_loss;

    /**
     * Delay before a salty bean changes hydration, measured in ticks.
     *
     * Zero applies the hydration change immediately. Effects from multiple
     * salty beans remain pending independently and can take effect on the same
     * tick.
     */
    uint32_t salty_bean_delay;

    /**
     * Immediate reward penalty for eating a bitter bean, in reward points.
     *
     * This value is subtracted from the reward. A positive value therefore
     * reduces the reward, while a negative value increases it.
     */
    float bitter_bean_penalty;

    /**
     * Spatial period of the blue sunlight pattern, measured in world cells.
     *
     * The blue channel varies smoothly and periodically across the world. This
     * value is the distance, along a seed-dependent direction, over which the
     * light completes one full bright-to-dark-to-bright cycle. Larger values
     * create broader bands of similar light. The value must be at least 1.
     */
    float sun_spatial_period;

    /**
     * Temporal period of the blue sunlight pattern, measured in ticks.
     *
     * At a fixed world cell, the light completes one full
     * bright-to-dark-to-bright cycle in this many ticks. The value must be
     * greater than zero.
     */
    uint32_t sun_cycle_duration;

    /**
     * Reward multiplier for blue sunlight at the agent's position.
     *
     * Each tick contributes \c sun_reward multiplied by the blue-channel value
     * divided by 255. A positive value rewards brighter light, a negative value
     * penalizes it, and zero disables the sunlight reward. The value is
     * measured in reward points at maximum blue intensity.
     */
    float sun_reward;
} xdgame_config_t;

/**
 * \brief Opaque game instance.
 */
typedef struct xdgame_state xdgame_state_t;

/**
 * \brief Opaque RGB map snapshot.
 *
 * Instances are returned by ::xdgame_generate_map() and released with
 * ::xdgame_free_map().
 */
typedef struct xdgame_map xdgame_map_t;

/**
 * \brief Action applied during one game tick.
 */
typedef enum xdgame_action
{
    XDGAME_NOP,         /**< Do not act. */
    XDGAME_MOVE_NORTH,  /**< Move one cell north. */
    XDGAME_MOVE_EAST,   /**< Move one cell east. */
    XDGAME_MOVE_SOUTH,  /**< Move one cell south. */
    XDGAME_MOVE_WEST,   /**< Move one cell west. */
    XDGAME_EAT_BEAN,    /**< Eat the bean under the agent. */
    XDGAME_PICKUP_BEAN, /**< Pick up the bean under the agent. */
    XDGAME_DROP_BEAN,   /**< Drop the carried bean under the agent. */
} xdgame_action_t;

/**
 * \brief Allocates a configuration initialized with default values.
 *
 * Release the returned configuration with ::xdgame_free_config().
 *
 * \return New configuration, or \c NULL on allocation failure.
 */
[[nodiscard]]
xdgame_config_t *xdgame_default_config(void);

/**
 * \brief Frees a configuration.
 *
 * Games initialized from \p cfg are unaffected because
 * ::xdgame_new_game() copies the configuration.
 *
 * \param cfg Configuration returned by ::xdgame_default_config().
 */
void xdgame_free_config(xdgame_config_t *cfg);

/**
 * \brief Creates a deterministic game.
 *
 * The configuration is copied and may be freed after this call. Release the
 * returned game with ::xdgame_free_game().
 *
 * \param seed Seed controlling procedural world generation.
 * \param cfg Configuration to copy.
 * \return New game, or \c NULL for invalid parameters or allocation failure.
 */
[[nodiscard]]
xdgame_state_t *xdgame_new_game(uint32_t seed, const xdgame_config_t *cfg);

/**
 * \brief Frees a game and its generated world data.
 *
 * This releases the field of view, generated patches, and pending game state
 * owned by \p game.
 *
 * \param game Game returned by ::xdgame_new_game().
 */
void xdgame_free_game(xdgame_state_t *game);

/**
 * \brief Generates an RGB map snapshot at a given position and time.
 *
 * Existing patches are read so prior bean interactions are visible. Missing
 * patches are generated temporarily and are not retained by \p game. The first
 * pixel is at (\p center_x - \p width / 2,
 * \p center_y - \p height / 2).
 *
 * Access the color channels with ::xdgame_get_map_r(),
 * ::xdgame_get_map_g(), and ::xdgame_get_map_b(). Query their dimensions with
 * ::xdgame_get_map_width() and ::xdgame_get_map_height(). Release the returned
 * map with ::xdgame_free_map().
 *
 * \param game Game returned by ::xdgame_new_game().
 * \param center_x Horizontal center coordinate.
 * \param center_y Vertical center coordinate.
 * \param width Map width in cells; must be non-zero.
 * \param height Map height in cells; must be non-zero.
 * \param t Tick used to evaluate sunlight.
 * \return New map, or \c NULL for invalid bounds or allocation failure.
 */
[[nodiscard]]
xdgame_map_t *xdgame_generate_map(xdgame_state_t *game,
                                  int32_t center_x,
                                  int32_t center_y,
                                  uint32_t width,
                                  uint32_t height,
                                  uint32_t t);

/**
 * \brief Frees an RGB map snapshot.
 *
 * This releases all three color channels owned by \p map.
 *
 * \param map Map returned by ::xdgame_generate_map().
 */
void xdgame_free_map(xdgame_map_t *map);

/**
 * \brief Returns the borrowed red map channel.
 *
 * The array contains width times height bytes and remains valid until \p map
 * is freed.
 *
 * \param map Map returned by ::xdgame_generate_map().
 * \return Read-only red channel.
 */
[[nodiscard]]
const uint8_t *xdgame_get_map_r(const xdgame_map_t *map);

/**
 * \brief Returns the borrowed green map channel.
 *
 * The array contains width times height bytes and remains valid until \p map
 * is freed.
 *
 * \param map Map returned by ::xdgame_generate_map().
 * \return Read-only green channel with width times height bytes.
 */
[[nodiscard]]
const uint8_t *xdgame_get_map_g(const xdgame_map_t *map);

/**
 * \brief Returns the borrowed blue map channel.
 *
 * The array contains width times height bytes and remains valid until \p map
 * is freed.
 *
 * \param map Map returned by ::xdgame_generate_map().
 * \return Read-only blue channel with width times height bytes.
 */
[[nodiscard]]
const uint8_t *xdgame_get_map_b(const xdgame_map_t *map);

/**
 * \brief Returns the map width.
 *
 * This is the number of pixels in each row of the color-channel arrays
 * returned by ::xdgame_get_map_r(), ::xdgame_get_map_g(), and
 * ::xdgame_get_map_b().
 *
 * \param map Map returned by ::xdgame_generate_map().
 * \return Width in cells.
 */
[[nodiscard]]
uint32_t xdgame_get_map_width(const xdgame_map_t *map);

/**
 * \brief Returns the map height.
 *
 * This is the number of rows in each color-channel array returned by
 * ::xdgame_get_map_r(), ::xdgame_get_map_g(), and ::xdgame_get_map_b().
 *
 * \param map Map returned by ::xdgame_generate_map().
 * \return Height in cells.
 */
[[nodiscard]]
uint32_t xdgame_get_map_height(const xdgame_map_t *map);

/**
 * \brief Places the agent and refreshes its field of view.
 *
 * Required patches are generated as needed. On failure, the agent position and
 * field of view remain unchanged.
 *
 * \param game Game returned by ::xdgame_new_game().
 * \param x New horizontal world coordinate.
 * \param y New vertical world coordinate.
 * \return Non-zero on success, otherwise zero.
 */
[[nodiscard]]
int xdgame_set_agent(xdgame_state_t *game, int32_t x, int32_t y);

/**
 * \brief Advances a game by one tick.
 *
 * Applies \p action, updates rewards and the field of view at the current
 * tick, and increments the internal tick counter before returning. Invalid or
 * inapplicable actions behave as no-ops. Query the resulting agent state with
 * ::xdgame_get_satiety_level(), ::xdgame_get_hydration_level(), and
 * ::xdgame_get_inventory_count(). For privileged evaluation, the bean flavor
 * eaten during this tick can be queried with
 * ::xdgame_reveal_last_eaten_flavor().
 *
 * \param game Game returned by ::xdgame_new_game().
 * \param action Action to apply.
 * \return Reward produced by this tick.
 */
float xdgame_tick(xdgame_state_t *game, xdgame_action_t action);

/**
 * \brief Returns the current satiety level.
 *
 * The value is initialized by ::xdgame_new_game() and updated by
 * ::xdgame_tick().
 *
 * \param game Game returned by ::xdgame_new_game().
 * \return Current satiety level.
 */
[[nodiscard]]
float xdgame_get_satiety_level(const xdgame_state_t *game);

/**
 * \brief Returns the current hydration level.
 *
 * The value is initialized by ::xdgame_new_game() and updated by
 * ::xdgame_tick().
 *
 * \param game Game returned by ::xdgame_new_game().
 * \return Current hydration level.
 */
[[nodiscard]]
float xdgame_get_hydration_level(const xdgame_state_t *game);

/**
 * \brief Returns the current inventory count.
 *
 * The agent can carry at most one bean. This function reports whether that
 * inventory slot is empty or occupied, but does not identify the bean flavor.
 *
 * \param game Game returned by ::xdgame_new_game().
 * \return \c 0 when the inventory is empty, otherwise \c 1.
 */
[[nodiscard]]
uint32_t xdgame_get_inventory_count(const xdgame_state_t *game);

/**
 * \brief Returns the bean flavor eaten during the most recently completed
 * tick.
 *
 * This is privileged evaluation information and is not part of the agent's
 * observation. It must not be used by an agent to select actions. Calling this
 * function does not modify or consume the stored value.
 *
 * The returned integer has the following meaning:
 *
 * - 0: No bean was eaten.
 * - 1: A satiety bean was eaten.
 * - 2: A hydration bean was eaten.
 * - 3: A salty bean was eaten.
 * - 4: A bitter bean was eaten.
 *
 * Before the first tick, this function returns 0.
 *
 * \param game Game returned by ::xdgame_new_game().
 * \return Flavor encoding for the most recently eaten bean.
 */
[[nodiscard]]
uint32_t xdgame_reveal_last_eaten_flavor(const xdgame_state_t *game);

/**
 * \brief Returns the borrowed red field-of-view channel.
 *
 * The array contains ::xdgame_fov_size() squared bytes, remains valid until
 * \p game is freed, and is overwritten by ::xdgame_tick() or
 * ::xdgame_set_agent().
 *
 * \param game Game returned by ::xdgame_new_game().
 * \return Read-only red channel.
 */
[[nodiscard]]
const uint8_t *xdgame_get_fov_r(const xdgame_state_t *game);

/**
 * \brief Returns the borrowed green field-of-view channel.
 *
 * The array contains ::xdgame_fov_size() squared bytes, remains valid until
 * \p game is freed, and is overwritten by ::xdgame_tick() or
 * ::xdgame_set_agent().
 *
 * \param game Game returned by ::xdgame_new_game().
 * \return Read-only green channel with ::xdgame_fov_size() squared bytes.
 */
[[nodiscard]]
const uint8_t *xdgame_get_fov_g(const xdgame_state_t *game);

/**
 * \brief Returns the borrowed blue field-of-view channel.
 *
 * The array contains ::xdgame_fov_size() squared bytes, remains valid until
 * \p game is freed, and is overwritten by ::xdgame_tick() or
 * ::xdgame_set_agent().
 *
 * \param game Game returned by ::xdgame_new_game().
 * \return Read-only blue channel with ::xdgame_fov_size() squared bytes.
 */
[[nodiscard]]
const uint8_t *xdgame_get_fov_b(const xdgame_state_t *game);

/**
 * \brief Returns the side length of the square field of view.
 *
 * Each channel returned by ::xdgame_get_fov_r(), ::xdgame_get_fov_g(), or
 * ::xdgame_get_fov_b() contains this value squared pixels. The returned
 * side length is always odd, so the field of view has one center pixel. That
 * pixel corresponds to the agent's world position, although the RGB channels
 * do not visually distinguish the agent from its cell.
 *
 * \param cfg Reserved for configuration-dependent sizes; may be \c NULL.
 * \return Field-of-view side length in cells.
 */
[[nodiscard]]
uint32_t xdgame_fov_size(const xdgame_config_t *cfg);

#ifdef __cplusplus
}
#endif

#endif // XDGAME_H
