import tomllib
from dataclasses import dataclass, fields, replace
from enum import IntEnum
from math import isfinite
from os import PathLike
from struct import Struct


class BeanVariants(IntEnum):
    """Select the number of possible colors for each bean flavor.

    Color variation does not change bean generation probabilities or gameplay
    effects.

    ``NO_BEAN_VARIANTS``
        Assign one fixed color to each flavor.

    ``FOUR_BEAN_VARIANTS``
        Permit four possible colors for each flavor.

    ``NINE_BEAN_VARIANTS``
        Permit nine possible colors for each flavor.
    """

    NO_BEAN_VARIANTS = 0
    FOUR_BEAN_VARIANTS = 1
    NINE_BEAN_VARIANTS = 2


_CONFIG_STRUCT = Struct("<ifIfffffIffIf")
_FLOAT_FIELDS = frozenset(
    {
        "bean_density",
        "needs_decay",
        "satiety_bean_satiety_gain",
        "hydration_bean_hydration_gain",
        "salty_bean_satiety_gain",
        "salty_bean_hydration_loss",
        "bitter_bean_penalty",
        "sun_spatial_period",
        "sun_reward",
    }
)
_INTEGER_FIELDS = frozenset(
    {"bean_biome_size", "salty_bean_delay", "sun_cycle_duration"}
)
_BEAN_VARIANTS_BY_NAME = {
    "one": BeanVariants.NO_BEAN_VARIANTS,
    "four": BeanVariants.FOUR_BEAN_VARIANTS,
    "nine": BeanVariants.NINE_BEAN_VARIANTS,
}
_BEAN_VARIANT_NAMES = {
    variant: name for name, variant in _BEAN_VARIANTS_BY_NAME.items()
}
_UINT32_MAX = (1 << 32) - 1
_INT32_MAX = (1 << 31) - 1


@dataclass(slots=True)
class Config:
    """Configuration loaded from a 10d_game WebAssembly module.

    Obtain instances with :func:`xdgame.default_config` or
    :func:`xdgame.config_from_toml`. Field names mirror ``xdgame_config_t`` from
    the C API. Floating-point values must be finite.

    Beans have four flavors. A satiety bean changes satiety immediately, a
    hydration bean changes hydration immediately, a salty bean changes satiety
    immediately and hydration after a delay, and a bitter bean applies an
    immediate reward penalty.

    :ivar bean_variants: Number of possible colors for each bean flavor. The
        value must be one of the three :class:`xdgame.BeanVariants` members:
        ``NO_BEAN_VARIANTS``, ``FOUR_BEAN_VARIANTS``, or ``NINE_BEAN_VARIANTS``.
        Their TOML spellings are ``"one"``, ``"four"``, and ``"nine"``,
        respectively.
    :ivar bean_density: Probability in ``[0, 1]`` that a generated world cell
        contains a bean. Each flavor is equally likely after a bean is placed.
    :ivar bean_biome_size: Side length of each square bean-color biome in world
        cells. The value must be in ``[1, 2147483647]``.
    :ivar needs_decay: Value subtracted from satiety and hydration every tick,
        in level points. Positive values decrease both levels; negative values
        increase them.
    :ivar satiety_bean_satiety_gain: Immediate satiety change, in level points,
        caused by a satiety bean. Positive values restore satiety; negative
        values reduce it.
    :ivar hydration_bean_hydration_gain: Immediate hydration change, in level
        points, caused by a hydration bean. Positive values restore hydration;
        negative values reduce it.
    :ivar salty_bean_satiety_gain: Immediate satiety change, in level points,
        caused by a salty bean. Positive values restore satiety; negative values
        reduce it.
    :ivar salty_bean_hydration_loss: Value subtracted from hydration after eating
        a salty bean. Positive values reduce hydration; negative values increase
        it.
    :ivar salty_bean_delay: Delay in ticks before a salty bean changes hydration.
        Zero applies the change immediately. The value must fit in ``uint32_t``.
    :ivar bitter_bean_penalty: Value subtracted from reward when a bitter bean is
        eaten. Positive values reduce reward; negative values increase it.
    :ivar sun_spatial_period: Spatial period of the blue sunlight pattern in
        world cells. Larger values produce broader bands of similar light. The
        value must be at least one.
    :ivar sun_cycle_duration: Temporal period of the sunlight pattern in ticks.
        The value must be a nonzero ``uint32_t``.
    :ivar sun_reward: Reward at maximum blue-light intensity. Positive values
        reward brighter light, negative values penalize it, and zero disables
        the sunlight reward.
    """

    bean_variants: BeanVariants
    bean_density: float
    bean_biome_size: int

    needs_decay: float

    satiety_bean_satiety_gain: float
    hydration_bean_hydration_gain: float
    salty_bean_satiety_gain: float
    salty_bean_hydration_loss: float
    salty_bean_delay: int
    bitter_bean_penalty: float

    sun_spatial_period: float
    sun_cycle_duration: int
    sun_reward: float

    def _with_toml(self, path: str | PathLike[str]) -> Config:
        with open(path, "rb") as file:
            values = tomllib.load(file)

        return self._with_overrides(values, bean_variants_as_name=True)

    def _with_overrides(
        self,
        values: dict[str, object],
        *,
        bean_variants_as_name: bool = False,
    ) -> Config:

        field_names = {field.name for field in fields(self)}
        unknown_fields = values.keys() - field_names
        if unknown_fields:
            names = ", ".join(sorted(unknown_fields))
            raise ValueError(f"unknown configuration field(s): {names}")

        updates: dict[str, object] = {}
        if "bean_variants" in values:
            variant = values["bean_variants"]
            if bean_variants_as_name:
                if not isinstance(variant, str):
                    raise TypeError("bean_variants must be a string")

                try:
                    updates["bean_variants"] = _BEAN_VARIANTS_BY_NAME[variant]
                except KeyError as error:
                    raise ValueError(
                        'bean_variants must be "one", "four", or "nine"'
                    ) from error
            elif isinstance(variant, BeanVariants):
                updates["bean_variants"] = variant
            else:
                raise TypeError("bean_variants must be a BeanVariants value")

        for name in _FLOAT_FIELDS & values.keys():
            value = values[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a number")

            value = float(value)
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")

            updates[name] = value

        for name in _INTEGER_FIELDS & values.keys():
            value = values[name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")

            updates[name] = value

        config = replace(self, **updates)
        if not 0.0 <= config.bean_density <= 1.0:
            raise ValueError("bean_density must be between 0 and 1")

        if not 1 <= config.bean_biome_size <= _INT32_MAX:
            raise ValueError("bean_biome_size must be between 1 and 2147483647")

        if not 0 <= config.salty_bean_delay <= _UINT32_MAX:
            raise ValueError("salty_bean_delay must fit in uint32_t")

        if config.sun_spatial_period < 1.0:
            raise ValueError("sun_spatial_period must be at least 1")

        if not 1 <= config.sun_cycle_duration <= _UINT32_MAX:
            raise ValueError("sun_cycle_duration must be between 1 and 4294967295")

        return config

    def to_toml(self, path: str | PathLike[str]) -> None:
        """Save the complete configuration as a TOML file.

        The resulting file can be loaded with :func:`xdgame.config_from_toml`.

        :param path: Destination path. An existing file is replaced.
        :raises OSError: If the file cannot be written.
        :raises ValueError: If ``bean_variants`` is invalid.
        """
        try:
            variant_name = _BEAN_VARIANT_NAMES[BeanVariants(self.bean_variants)]
        except (KeyError, ValueError) as error:
            raise ValueError("bean_variants is invalid") from error

        contents = (
            f'bean_variants = "{variant_name}"\n'
            f"bean_density = {self.bean_density!r}\n"
            f"bean_biome_size = {self.bean_biome_size}\n"
            "\n"
            f"needs_decay = {self.needs_decay!r}\n"
            "\n"
            f"satiety_bean_satiety_gain = {self.satiety_bean_satiety_gain!r}\n"
            f"hydration_bean_hydration_gain = {self.hydration_bean_hydration_gain!r}\n"
            f"salty_bean_satiety_gain = {self.salty_bean_satiety_gain!r}\n"
            f"salty_bean_hydration_loss = {self.salty_bean_hydration_loss!r}\n"
            f"salty_bean_delay = {self.salty_bean_delay}\n"
            f"bitter_bean_penalty = {self.bitter_bean_penalty!r}\n"
            "\n"
            f"sun_spatial_period = {self.sun_spatial_period!r}\n"
            f"sun_cycle_duration = {self.sun_cycle_duration}\n"
            f"sun_reward = {self.sun_reward!r}\n"
        )
        with open(path, "w", encoding="utf-8", newline="\n") as file:
            file.write(contents)

    def _to_bytes(self) -> bytes:
        return _CONFIG_STRUCT.pack(
            int(self.bean_variants),
            self.bean_density,
            self.bean_biome_size,
            self.needs_decay,
            self.satiety_bean_satiety_gain,
            self.hydration_bean_hydration_gain,
            self.salty_bean_satiety_gain,
            self.salty_bean_hydration_loss,
            self.salty_bean_delay,
            self.bitter_bean_penalty,
            self.sun_spatial_period,
            self.sun_cycle_duration,
            self.sun_reward,
        )

    @classmethod
    def _from_bytes(cls, data: bytes | bytearray) -> Config:
        (
            bean_variants,
            bean_density,
            bean_biome_size,
            needs_decay,
            satiety_bean_satiety_gain,
            hydration_bean_hydration_gain,
            salty_bean_satiety_gain,
            salty_bean_hydration_loss,
            salty_bean_delay,
            bitter_bean_penalty,
            sun_spatial_period,
            sun_cycle_duration,
            sun_reward,
        ) = _CONFIG_STRUCT.unpack(data)

        return cls(
            bean_variants=BeanVariants(bean_variants),
            bean_density=bean_density,
            bean_biome_size=bean_biome_size,
            needs_decay=needs_decay,
            satiety_bean_satiety_gain=satiety_bean_satiety_gain,
            hydration_bean_hydration_gain=hydration_bean_hydration_gain,
            salty_bean_satiety_gain=salty_bean_satiety_gain,
            salty_bean_hydration_loss=salty_bean_hydration_loss,
            salty_bean_delay=salty_bean_delay,
            bitter_bean_penalty=bitter_bean_penalty,
            sun_spatial_period=sun_spatial_period,
            sun_cycle_duration=sun_cycle_duration,
            sun_reward=sun_reward,
        )


CONFIG_SIZE = _CONFIG_STRUCT.size
