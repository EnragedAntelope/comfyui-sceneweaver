"""comfyui-sceneweaver - V3 custom node pack entrypoint.

Exposes two nodes per genre -- the sci-fi pair and the fantasy pair:

* ``Scene Weaver - Sci-Fi`` (``SceneWeaverSciFi``) - the core node, complete on
  its own. One click gives an environment, up to four entities and the
  relationships between them, as prose plus structured JSON.
* ``Scene Entity - Sci-Fi`` (``SceneEntitySciFi``) - an optional layer node that
  describes one entity in full depth and emits a ``SCENE_ENTITY`` payload. Wire
  it into a Scene Weaver slot to promote that slot; nothing requires it.
* ``Scene Weaver - Fantasy`` / ``Scene Entity - Fantasy`` -- the same pair,
  generated from the fantasy pack. An entity of either genre wires into a scene
  of either genre.

**Genre is node identity, never a wire.** Both classes are *generated* from a
``GenrePack`` (``data/genre.py``), and this file is the only place a concrete
genre is named. Adding one is a data module plus the two registration lines
below - ``tests/test_genre_contract.py`` pins that seam.
"""
import logging

from comfy_api.latest import ComfyExtension, io

#: Runtime messages go to the logger, not stdout. ComfyUI owns root logging
#: configuration, so this pack deliberately installs no handler and never calls
#: logging.basicConfig(). The logger NAME carries what a '[NodeName]' message
#: prefix would have said.
_LOG = logging.getLogger(__name__)

# Package-relative inside ComfyUI; absolute fallback keeps the entrypoint
# importable in flatter layouts (and under the tests' module loader).
try:
    from .data.genre import ENTITY_NODE_SLOTS, SCENE_NODE_SLOTS
    from .data.fantasy import FANTASY_PACK as _FANTASY_BUILTINS
    from .data.horror import HORROR_PACK as _HORROR_BUILTINS
    from .data.scifi import SCIFI_PACK as _SCIFI_BUILTINS
    from .data.user_options import apply_user_options
    from .nodes.frontend import register_routes
    from .nodes.scene_entity import build_entity_node
    from .nodes.scene_weaver import build_scene_node
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import ENTITY_NODE_SLOTS, SCENE_NODE_SLOTS
    from data.fantasy import FANTASY_PACK as _FANTASY_BUILTINS
    from data.horror import HORROR_PACK as _HORROR_BUILTINS
    from data.scifi import SCIFI_PACK as _SCIFI_BUILTINS
    from data.user_options import apply_user_options
    from nodes.frontend import register_routes
    from nodes.scene_entity import build_entity_node
    from nodes.scene_weaver import build_scene_node

# --- User options -----------------------------------------------------------
# The one place the optional, gitignored user_options.json is merged: after the
# pack is imported and before any node class is generated from it, so added
# values reach the widgets, the random draws and the frontend route alike.
#
# Deliberately NOT inside data/scifi.py. `import data.scifi` must yield the
# built-ins and only the built-ins, or a check script that imported the data
# layer would bake a maintainer's private entries into a committed file
# (`feedback-generator-cannot-leak-user-data`). scripts/builtin_options.py is
# the ast-based reader that such a script uses instead.
#: The top-level pools/tags are sci-fi's; every other genre has its own section.
_GENRE_SECTIONS = ("fantasy", "horror")
SCIFI_PACK = apply_user_options(_SCIFI_BUILTINS, sections=_GENRE_SECTIONS)
FANTASY_PACK = apply_user_options(_FANTASY_BUILTINS, section="fantasy")
HORROR_PACK = apply_user_options(_HORROR_BUILTINS, section="horror")

# --- Genre registration -----------------------------------------------------
# Two lines per genre. A second genre adds its own data/<genre>.py and two more.
SceneEntitySciFi = build_entity_node(SCIFI_PACK)
SceneWeaverSciFi = build_scene_node(SCIFI_PACK)
SceneEntityFantasy = build_entity_node(FANTASY_PACK)
SceneWeaverFantasy = build_scene_node(FANTASY_PACK)
SceneEntityHorror = build_entity_node(HORROR_PACK)
SceneWeaverHorror = build_scene_node(HORROR_PACK)

#: Which pack, at which slot count, each registered node id was built from. The
#: frontend route reads this to serve per-kind labels and kind-scoped pools; it
#: is the same two-lines-per-genre registration seen from the other side.
NODE_PACKS = {
    "SceneWeaverSciFi": (SCIFI_PACK, SCENE_NODE_SLOTS),
    "SceneEntitySciFi": (SCIFI_PACK, ENTITY_NODE_SLOTS),
    "SceneWeaverFantasy": (FANTASY_PACK, SCENE_NODE_SLOTS),
    "SceneEntityFantasy": (FANTASY_PACK, ENTITY_NODE_SLOTS),
    "SceneWeaverHorror": (HORROR_PACK, SCENE_NODE_SLOTS),
    "SceneEntityHorror": (HORROR_PACK, ENTITY_NODE_SLOTS),
}

#: Serves js/sceneweaver.js its label and pool data. No-op without a ComfyUI
#: server, and the frontend degrades to generic labels if it is missing -- so a
#: failure here can never stop the nodes registering.
ROUTES_REGISTERED = register_routes(NODE_PACKS)

#: Tells ComfyUI where to find this pack's frontend JavaScript.
WEB_DIRECTORY = "./js"

__all__ = [
    "comfy_entrypoint",
    "NODE_PACKS",
    "ROUTES_REGISTERED",
    "WEB_DIRECTORY",
    "SceneWeaverExtension",
    "SceneWeaverSciFi",
    "SceneEntitySciFi",
    "SceneWeaverFantasy",
    "SceneEntityFantasy",
    "SceneWeaverHorror",
    "SceneEntityHorror",
]


class SceneWeaverExtension(ComfyExtension):
    """Registers the SceneWeaver node pack with ComfyUI."""

    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            SceneWeaverSciFi, SceneEntitySciFi, SceneWeaverFantasy, SceneEntityFantasy,
            SceneWeaverHorror, SceneEntityHorror,
        ]


async def comfy_entrypoint() -> SceneWeaverExtension:
    return SceneWeaverExtension()
