from importlib.metadata import version as distribution_version

from sphinx.ext.intersphinx import resolve_reference_in_inventory

project = "xdgame"
release = distribution_version("xdgame")
version = release

extensions = ["sphinx.ext.autodoc", "sphinx.ext.intersphinx"]

intersphinx_mapping = {
    "numpy": ("https://numpy.org/doc/stable/", None),
    "python": ("https://docs.python.org/3/", None),
}
nitpicky = True

_NUMPY_XREF_ALIASES = {
    "numpy._typing._array_like.NDArray": ("data", "numpy.typing.NDArray"),
    "numpy.typing.NDArray": ("data", "numpy.typing.NDArray"),
    "numpy.uint8": ("attr", "numpy.uint8"),
}


def _resolve_numpy_type(app, env, node, contnode):
    del app
    alias = _NUMPY_XREF_ALIASES.get(node.get("reftarget"))
    if alias is None:
        return None

    reftype, target = alias
    original_reftype = node["reftype"]
    original_target = node["reftarget"]
    try:
        node["reftype"] = reftype
        node["reftarget"] = target
        return resolve_reference_in_inventory(env, "numpy", node, contnode)

    finally:
        node["reftype"] = original_reftype
        node["reftarget"] = original_target


def setup(app):
    app.connect("missing-reference", _resolve_numpy_type)


autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_typehints_format = "short"

exclude_patterns = ["_build"]
html_theme = "alabaster"
