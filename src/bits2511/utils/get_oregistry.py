"""
Provide an import for the oregistry.

Example::

    from bits2511.utils.get_oregistry import oregistry
"""

from apsbits.core.instrument_init import with_registry


@with_registry
def _getit(oregistry):
    """Get from the decorator."""
    return oregistry

oregistry = _getit()
"""Ophyd object registry from guarneri Instrument."""
