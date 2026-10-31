"""Dataset loaders and their registry.

A loader turns a local file (or a bundled literal) into a
:class:`~semantica.benchmarks.types.Dataset`. Loaders are registered by name so
the CLI and the runner can enumerate what is available without importing each
module by hand:

    >>> from semantica.benchmarks import datasets
    >>> datasets.list_datasets()            # doctest: +SKIP
    ['hotpotqa', 'locomo', 'musique', 'sample']

Licences differ per dataset and the harness never downloads or redistributes
data — the user supplies the file. See each loader's docstring.
"""

from typing import Callable, Dict, List

from ..types import Dataset

LOADERS: Dict[str, Callable[..., Dataset]] = {}


def register_dataset(name: str, loader: Callable[..., Dataset]) -> None:
    """Register ``loader`` under ``name`` (overwrites a same-named entry)."""
    LOADERS[name] = loader


def list_datasets() -> List[str]:
    """Registered dataset names, sorted."""
    return sorted(LOADERS)


def get_loader(name: str) -> Callable[..., Dataset]:
    """Return the loader for ``name`` or raise ``KeyError`` with the options."""
    if name not in LOADERS:
        raise KeyError(
            f"unknown dataset {name!r}. Registered: {list_datasets()}"
        )
    return LOADERS[name]


def load_dataset(name: str, **options) -> Dataset:
    """Load a registered dataset by name, forwarding ``**options``."""
    return get_loader(name)(**options)


# Importing these modules runs their ``register_dataset`` calls. Kept at the
# bottom so the registry names above exist before any loader imports them.
from . import hotpotqa, locomo, musique, sample  # noqa: E402,F401
